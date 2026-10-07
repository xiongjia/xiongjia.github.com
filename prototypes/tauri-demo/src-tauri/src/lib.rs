//! Tauri commands exposed to the frontend.
//!
//! `system_snapshot` samples the machine and appends the point to the history
//! buffer (subject to the minimum spacing guard in [`metrics`]);
//! `system_history` returns the buffer for the line chart.
//!
//! Errors cross the IPC boundary as plain strings: this demo has a single
//! failure mode (a poisoned lock), so a typed error would not buy anything.

mod metrics;

use metrics::{HistoryPoint, MetricsState, Snapshot};
use tauri::State;

#[tauri::command]
fn system_snapshot(state: State<'_, MetricsState>) -> Result<Snapshot, String> {
    state.snapshot().map_err(|error| error.to_string())
}

#[tauri::command]
fn system_history(state: State<'_, MetricsState>) -> Result<Vec<HistoryPoint>, String> {
    state.history().map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(MetricsState::new())
        .invoke_handler(tauri::generate_handler![system_snapshot, system_history])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
