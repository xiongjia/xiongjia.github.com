//! Binary codecs for the two record formats on disk.
//!
//! * **data record** — one append-only entry in a `*.data` file:
//!   `CRC32(4) | timestamp(4) | key size(2) | value size(4) | key | value`.
//!   The CRC32 covers everything after the CRC itself (header tail + key +
//!   value), which is what lets the loader detect a torn or damaged tail.
//! * **hint record** — a value-less entry in a `*.hint` file written by
//!   `merge`: `timestamp(4) | key size(2) | value size(4) | offset(8) | key`.
//!   Rebuilding the keydir from hint records avoids reading every value.
//!
//! Deletions are tombstone records: `value size = 0xFFFF_FFFF` and no value
//! bytes. A normal record with `value size = 0` therefore still means "empty
//! value", not "deleted".

use std::io::Read;

use crate::error::{Error, Result};

/// Fixed size of a data record header: `4 + 4 + 2 + 4` (same as the paper).
pub const HEADER_SIZE: usize = 14;

/// Fixed size of a hint record header: `4 + 2 + 4 + 8`.
pub const HINT_HEADER_SIZE: usize = 18;

/// Key length limit: the key-size field is 2 bytes wide.
pub const MAX_KEY_SIZE: usize = u16::MAX as usize;

/// Value length limit: `0xFFFF_FFFF` is reserved as the tombstone marker.
pub const MAX_VALUE_SIZE: usize = u32::MAX as usize - 1;

/// Sentinel stored in the value-size field for a deletion marker.
pub const TOMBSTONE: u32 = u32::MAX;

/// A logical log entry (tombstone when `value` is `None`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LogRecord {
    pub timestamp: u32,
    pub key: Vec<u8>,
    pub value: Option<Vec<u8>>,
}

impl LogRecord {
    /// Whether this record marks a deletion (no value bytes follow).
    pub fn is_tombstone(&self) -> bool {
        self.value.is_none()
    }

    /// Value size as it appears in the header (the tombstone sentinel for a
    /// deletion).
    pub fn value_size(&self) -> u32 {
        match &self.value {
            Some(value) => value.len() as u32,
            None => TOMBSTONE,
        }
    }
}

/// A decoded data record plus its on-disk size (header + key + value), which
/// the loader uses to advance the offset.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodedRecord {
    pub record: LogRecord,
    pub size: u64,
}

/// A decoded hint record plus its on-disk size.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodedHint {
    pub record: HintRecord,
    pub size: u64,
}

/// One hint entry: where the latest version of a key lives in its data file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HintRecord {
    pub timestamp: u32,
    pub key_size: u16,
    pub value_size: u32,
    pub offset: u64,
    pub key: Vec<u8>,
}

impl HintRecord {
    /// Bytes this hint record occupies on disk.
    pub fn encoded_len(&self) -> usize {
        HINT_HEADER_SIZE + self.key.len()
    }
}

/// Little-endian integer helpers for the fixed-width header fields.
///
/// The offsets are compile-time constants inside headers of exactly these
/// widths, so the copies cannot fail; doing it this way keeps the decoders free
/// of `expect` calls.
#[inline]
fn read_u16(buffer: &[u8], at: usize) -> u16 {
    let mut bytes = [0u8; 2];
    bytes.copy_from_slice(&buffer[at..at + 2]);
    u16::from_le_bytes(bytes)
}

#[inline]
fn read_u32(buffer: &[u8], at: usize) -> u32 {
    let mut bytes = [0u8; 4];
    bytes.copy_from_slice(&buffer[at..at + 4]);
    u32::from_le_bytes(bytes)
}

#[inline]
fn read_u64(buffer: &[u8], at: usize) -> u64 {
    let mut bytes = [0u8; 8];
    bytes.copy_from_slice(&buffer[at..at + 8]);
    u64::from_le_bytes(bytes)
}

/// `crc32fast::hash` as a plain function, used by tests and by `encode`.
pub fn crc32(bytes: &[u8]) -> u32 {
    crc32fast::hash(bytes)
}

/// Encode one data record. `value = None` writes a tombstone.
pub fn encode(timestamp: u32, key: &[u8], value: Option<&[u8]>) -> Vec<u8> {
    let value_size = match value {
        Some(value) => value.len() as u32,
        None => TOMBSTONE,
    };
    let value_len = value.map_or(0, <[u8]>::len);
    let mut buffer = Vec::with_capacity(HEADER_SIZE + key.len() + value_len);

    buffer.extend_from_slice(&0u32.to_le_bytes()); // CRC32 placeholder
    buffer.extend_from_slice(&timestamp.to_le_bytes());
    buffer.extend_from_slice(&(key.len() as u16).to_le_bytes());
    buffer.extend_from_slice(&value_size.to_le_bytes());
    buffer.extend_from_slice(key);
    if let Some(value) = value {
        buffer.extend_from_slice(value);
    }

    let checksum = crc32(&buffer[4..]);
    buffer[..4].copy_from_slice(&checksum.to_le_bytes());
    buffer
}

/// Decode the next data record.
///
/// `file_len` is the total size of the file being read: the declared key and
/// value sizes are checked against the bytes that are actually left *before*
/// anything is allocated, so a damaged or torn header cannot ask the decoder
/// for a multi-gigabyte buffer.
///
/// Returns `Ok(None)` on a clean end of file. A partial header/body, a length
/// that does not fit, or a CRC mismatch returns [`Error::Corrupt`]: the caller
/// decides whether that is a torn tail to truncate (the active file) or a real
/// error.
pub fn decode(
    mut reader: impl Read,
    file_id: u32,
    offset: u64,
    file_len: u64,
) -> Result<Option<DecodedRecord>> {
    let mut header = [0u8; HEADER_SIZE];
    match fill(&mut reader, &mut header)? {
        ReadOutcome::Eof => return Ok(None),
        ReadOutcome::Short => {
            return Err(Error::corrupt(file_id, offset, "truncated record header"));
        }
        ReadOutcome::Full => {}
    }

    let expected_crc = read_u32(&header, 0);
    let timestamp = read_u32(&header, 4);
    let key_size = read_u16(&header, 8);
    let value_size = read_u32(&header, 10);

    if key_size == 0 {
        return Err(Error::corrupt(file_id, offset, "record has an empty key"));
    }

    // Tombstones carry no value bytes; every other length must fit in what is
    // left of the file, otherwise the header is garbage and the body would be
    // an unbounded allocation.
    let value_len = if value_size == TOMBSTONE {
        0
    } else {
        u64::from(value_size)
    };
    let record_len = HEADER_SIZE as u64 + u64::from(key_size) + value_len;
    let remaining = file_len.saturating_sub(offset);
    if record_len > remaining {
        return Err(Error::corrupt(
            file_id,
            offset,
            format!("record needs {record_len} bytes but only {remaining} are left in the file"),
        ));
    }

    let mut key = vec![0u8; key_size as usize];
    require(&mut reader, &mut key, file_id, offset, "key")?;

    let value = if value_size == TOMBSTONE {
        None
    } else {
        let mut value = vec![0u8; value_size as usize];
        require(&mut reader, &mut value, file_id, offset, "value")?;
        Some(value)
    };

    let mut hasher = crc32fast::Hasher::new();
    hasher.update(&header[4..]);
    hasher.update(&key);
    if let Some(value) = &value {
        hasher.update(value);
    }
    if hasher.finalize() != expected_crc {
        return Err(Error::corrupt(
            file_id,
            offset,
            format!("CRC32 mismatch (header says {expected_crc:#010x})"),
        ));
    }

    let size = HEADER_SIZE as u64 + u64::from(key_size) + value.as_ref().map_or(0, Vec::len) as u64;
    Ok(Some(DecodedRecord {
        record: LogRecord {
            timestamp,
            key,
            value,
        },
        size,
    }))
}

/// Encode one hint record.
pub fn encode_hint(record: &HintRecord) -> Vec<u8> {
    let mut buffer = Vec::with_capacity(record.encoded_len());
    buffer.extend_from_slice(&record.timestamp.to_le_bytes());
    buffer.extend_from_slice(&record.key_size.to_le_bytes());
    buffer.extend_from_slice(&record.value_size.to_le_bytes());
    buffer.extend_from_slice(&record.offset.to_le_bytes());
    buffer.extend_from_slice(&record.key);
    buffer
}

/// Decode the next hint record (`Ok(None)` at a clean end of file).
///
/// `hint_len` is the total size of the hint file; like [`decode`], the key size
/// is validated against the bytes left before allocating.
pub fn decode_hint(
    mut reader: impl Read,
    file_id: u32,
    offset: u64,
    hint_len: u64,
) -> Result<Option<DecodedHint>> {
    let mut header = [0u8; HINT_HEADER_SIZE];
    match fill(&mut reader, &mut header)? {
        ReadOutcome::Eof => return Ok(None),
        ReadOutcome::Short => {
            return Err(Error::corrupt(file_id, offset, "truncated hint header"));
        }
        ReadOutcome::Full => {}
    }

    let timestamp = read_u32(&header, 0);
    let key_size = read_u16(&header, 4);
    let value_size = read_u32(&header, 6);
    let record_offset = read_u64(&header, 10);

    if key_size == 0 {
        return Err(Error::corrupt(
            file_id,
            offset,
            "hint record has an empty key",
        ));
    }

    let hint_len_total = HINT_HEADER_SIZE as u64 + u64::from(key_size);
    let remaining = hint_len.saturating_sub(offset);
    if hint_len_total > remaining {
        return Err(Error::corrupt(
            file_id,
            offset,
            format!("hint record needs {hint_len_total} bytes but only {remaining} are left"),
        ));
    }

    let mut key = vec![0u8; key_size as usize];
    require(&mut reader, &mut key, file_id, offset, "key")?;

    Ok(Some(DecodedHint {
        record: HintRecord {
            timestamp,
            key_size,
            value_size,
            offset: record_offset,
            key,
        },
        size: HINT_HEADER_SIZE as u64 + key_size as u64,
    }))
}

/// Outcome of trying to fill a fixed-size buffer from a log file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ReadOutcome {
    /// Zero bytes were available: a clean end of file.
    Eof,
    /// Some bytes, but fewer than requested: a torn tail record.
    Short,
    /// The buffer was filled completely.
    Full,
}

/// Fill `buffer` completely, distinguishing EOF from a short (torn) read and
/// propagating real I/O errors instead of hiding them as end of file.
fn fill(reader: &mut impl Read, buffer: &mut [u8]) -> Result<ReadOutcome> {
    let mut filled = 0;
    while filled < buffer.len() {
        match reader.read(&mut buffer[filled..]) {
            Ok(0) => break,
            Ok(n) => filled += n,
            Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(Error::io(error)),
        }
    }
    Ok(match (filled, buffer.is_empty()) {
        (0, false) => ReadOutcome::Eof,
        (n, _) if n == buffer.len() => ReadOutcome::Full,
        _ => ReadOutcome::Short,
    })
}

/// Read a body field that must be present (the header already parsed), turning
/// a short read into a corruption error.
fn require(
    reader: &mut impl Read,
    buffer: &mut [u8],
    file_id: u32,
    offset: u64,
    what: &str,
) -> Result<()> {
    if fill(reader, buffer)? == ReadOutcome::Full {
        Ok(())
    } else {
        Err(Error::corrupt(
            file_id,
            offset,
            format!("truncated {what}: expected {} bytes", buffer.len()),
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn data_record_roundtrip() {
        let encoded = encode(42, b"user:1", Some(b"alice"));
        assert_eq!(encoded.len(), HEADER_SIZE + 6 + 5);

        let decoded = decode(Cursor::new(&encoded), 0, 0, encoded.len() as u64).expect("decode");
        let decoded = decoded.expect("one record");
        assert_eq!(decoded.size, encoded.len() as u64);
        assert_eq!(decoded.record.timestamp, 42);
        assert_eq!(decoded.record.key, b"user:1");
        assert_eq!(decoded.record.value.as_deref(), Some(&b"alice"[..]));
        assert!(!decoded.record.is_tombstone());
    }

    #[test]
    fn tombstone_roundtrip() {
        let encoded = encode(7, b"gone", None);
        // A tombstone has no value bytes, but keeps the normal header.
        assert_eq!(encoded.len(), HEADER_SIZE + 4);
        let decoded = decode(Cursor::new(&encoded), 0, 0, encoded.len() as u64)
            .expect("decode")
            .expect("record");
        assert!(decoded.record.is_tombstone());
        assert_eq!(decoded.record.value_size(), TOMBSTONE);
    }

    #[test]
    fn empty_value_is_not_a_tombstone() {
        let encoded = encode(1, b"empty", Some(b""));
        let decoded = decode(Cursor::new(&encoded), 0, 0, encoded.len() as u64)
            .expect("decode")
            .expect("record");
        assert_eq!(decoded.record.value.as_deref(), Some(&b""[..]));
        assert!(!decoded.record.is_tombstone());
    }

    #[test]
    fn clean_eof_returns_none() {
        assert!(decode(Cursor::new(Vec::<u8>::new()), 0, 0, 0)
            .expect("decode")
            .is_none());
    }

    #[test]
    fn crc_mismatch_is_detected() {
        let mut encoded = encode(1, b"k", Some(b"v"));
        let last = encoded.len() - 1;
        encoded[last] ^= 0xff; // flip a value bit
        let error =
            decode(Cursor::new(&encoded), 3, 0, encoded.len() as u64).expect_err("should fail");
        assert!(
            matches!(error, Error::Corrupt { file_id: 3, .. }),
            "{error}"
        );
    }

    #[test]
    fn truncated_tail_is_detected() {
        let encoded = encode(1, b"k", Some(b"value"));
        let truncated = &encoded[..encoded.len() - 2];
        assert!(decode(Cursor::new(truncated), 0, 0, truncated.len() as u64).is_err());
    }

    #[test]
    fn oversized_length_is_rejected_before_allocating() {
        // A damaged header claiming a ~4 GiB value must be rejected by the
        // length check instead of becoming a huge allocation.
        let mut encoded = encode(1, b"k", Some(b"v"));
        encoded[10..14].copy_from_slice(&0xFFFF_FFFEu32.to_le_bytes());
        let error = decode(Cursor::new(&encoded), 0, 0, encoded.len() as u64).expect_err("fail");
        assert!(matches!(error, Error::Corrupt { .. }), "{error}");
    }

    #[test]
    fn oversized_hint_key_is_rejected() {
        let hint = HintRecord {
            timestamp: 1,
            key_size: 200,
            value_size: 1,
            offset: 0,
            key: vec![b'k'; 200],
        };
        let mut encoded = encode_hint(&hint);
        encoded.truncate(HINT_HEADER_SIZE + 10); // claim a 200-byte key in a 28-byte file
        assert!(decode_hint(Cursor::new(&encoded), 0, 0, encoded.len() as u64).is_err());
    }

    #[test]
    fn empty_key_is_rejected() {
        let encoded = encode(1, b"", Some(b"v"));
        assert!(decode(Cursor::new(&encoded), 0, 0, encoded.len() as u64).is_err());
    }

    #[test]
    fn hint_record_roundtrip() {
        let hint = HintRecord {
            timestamp: 11,
            key_size: 3,
            value_size: 5,
            offset: 1024,
            key: b"abc".to_vec(),
        };
        let encoded = encode_hint(&hint);
        assert_eq!(encoded.len(), hint.encoded_len());
        let decoded = decode_hint(Cursor::new(&encoded), 0, 0, encoded.len() as u64)
            .expect("decode")
            .expect("record");
        assert_eq!(decoded.record, hint);
        assert_eq!(decoded.size, encoded.len() as u64);
    }
}
