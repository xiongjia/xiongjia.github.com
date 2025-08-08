---
tags: [tech,dev,protobuf]
---

# protobuf

- [developers page](https://developers.google.com/protocol-buffers/){:target="_blank"}
- [developers docs](https://developers.google.com/protocol-buffers/docs/overview){:target="_blank"}

## 优缺点

- 比 JSON 占用的存储空间更小，解析更快。
- 适合整个能被加载到内存的结构。如果内存占用过大的结构 （比如几十、几百 MB）就不适合用 protobuf。
- 二进制输出流没有压缩。

## .proto 定义

- [Language Guide (proto3)](https://developers.google.com/protocol-buffers/docs/proto3){:target="_blank"}
- [Language Guide (proto2)](https://developers.google.com/protocol-buffers/docs/proto){:target="_blank"}

## 实践

- [C++ 中调用 protobuf](https://github.com/xiongjia/recycle.bin/tree/master/scratch/misc/protobuf){:target="_blank"}
- [golang 中调用 protobuf](https://github.com/xiongjia/recycle.bin/tree/master/scratch/misc/protobuf-go){:target="_blank"}

## Others

- [3 party addons](https://github.com/protocolbuffers/protobuf/blob/master/docs/third_party.md){:target="_blank"}
