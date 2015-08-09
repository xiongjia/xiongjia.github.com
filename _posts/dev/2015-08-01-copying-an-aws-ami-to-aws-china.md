---
layout: post
title: "遷移 AWS AMI 到 AWS China"
description: ""
category: dev
tags: [dev, tips, aws, ec2]
---
{% include JB/setup %}

前一段工作的產品開通了 AWS China (cn-north-1) 的 Region。    
於是便需要把原先其它 AWS Regions 的 AMI Copy 到 China。      
(AMI: Amazon Machine Images。產品的部署都存放在了對應的 AMI 中。)

由於某些衆所周知的原因， AWS China 與 AWS 其它 Regions 之間是分離的。
於是乎便不能用 AWS 提供的 AMI Copy 工具去複製這些個 images 到 China。

折騰了半天，還咨詢了 AWS 客服。總算是 Copy 過來了。
下面記錄一下當時大概的流程:

----

# 基本思路
基本思路可以分爲 2 部分

1. 在 source region "導出": 把 AMI 導出至一個 file,並把該 file 傳送到 AWS China。 
   - 由於不能直接讀取 AMI 數據，所以需要用對應的 AMI 啓動一台機器。
     隨後用 Linux `dd` 命令把該 AMI 生成的 root device 生成文件。

2. 在 AWS China "導入": 拿到這個 file 后，用其生成一個 AMI 
   - 拿到這個文件后不能直接產生 AMI 。需要用 `dd` 將它寫回到一個 EBS Volume 上。
     之後間接把這個 EBS Volume 做出 AMI。
   - 最後 AWS China 就可以得到一個相應的 AMI

# 注意事項
1. AWS AMI 有 2 种 Virtualization 類型: `hvm` & `paravirtual`     
   目前此方法只能用於 `hvm` 的 AMI images。 不可以用在 `paravirtual` images 上。
   (原因主要在於 OS 的 Bootloader。 `paravirtual` 似乎用了 Xen 之類的虛擬技術，
   如果這樣 `dd` 回去据我測試會導致無法啓動。)

2. AWS 的 EBS Volume 只能被 mount 到同一個 AZ (Availability Zones)  的 Instance 上。   
   (創建前請注意核對, 最好把操作中 Instances 和 Volumes 都放在同一個 AZ 裏。)

3. 導出的文件會比較大, Windows OS ~12G+ (壓縮后), Linux ~4G+ (壓縮后)。
   在傳到 China 時會過某 "結界"。如果用 `scp` 感覺幾天都 copy 不完。 `ftp` 可能好一點。    
   還有一種加速方法是用，`tsunami` 快速的 udp transfer 。
   (會造成大量帶寬浪費，參考我之前記錄的 [tsunami udp file transfer]({% post_url dev/2015-07-25-tsunami-udp-file-transfer %}) )

# Linux AMI 的遷移

- AMI 導出到 file 
1. 把要 Copy 的 AIM 啓動成一個 Instance。(這裏可以登上這台機器察看一下，是不是你的 AMI)
2. Stop 該 Instance, 找到 root device 所在的 Volume。把它 Detach 出來。(這個就是 source volume 了)
3. 有了這個 Volume 后整個 Instance 可以 terminate 掉了
4. 在同一個 AZ 裏啓動一個新的 Instance. 把剛才的 Volume attach 到這個新的 Instance 上。
4. 創建一個足夠大的 Volume 用來存放, `dd` 導出的文件。並把這個 Volume attach 到剛才新開的 Instance 上。
5. 登到這個新的 Instance 上，用 `sudo fdisk -l` 察看你的 Volumes. 這是應該有 3 個 volumes。
   從大小和設備名大概能看出是哪個 volume。   
   比如: 這裏有 
   - `/dev/xvda` (7G) 當前 Instance 的 root device
   - `/dev/xvdf` (100G) 是用來存儲導出導出數據的 volume
   - `/dev/xvdh` (7G) 是 `dd` 的 source
7. 把準備的空間格式化並 mount，比如格式化 100G 的 `/dev/xvdf`:   
   `sudo mkfs.ext4 /dev/xvdf; sudo mount /dev/xvdf /mnt`
8. 用 `dd` 到處 AMI 數據。這裡爲了方便用 pipe 壓縮最好用 root account, 比如:    
   `dd if=/dev/xvdh | gzip > /mnt/root.img`
9. 完成后用傳輸工具傳送到 AWS China。(參考之前`注意事項`裏說的)

- 在 AWS China 將 image 文件做成 AMI
1. 啓動一個 Linux Instance 在 AWS China   
2. 創建一個足夠大小的 EBS Volume, attache 到 Linux Instance 上。
   (這個大小取決於 Source AMI Linux Volume 大小，最好和他一樣大。不能比它小)
3. 在 China 這個 Linux instance 上用 `dd` 把 image 文件寫回剛才 mount 的設備上。
4. (可選) Mount 出 `dd` 的 image 檢查 Bootloader 是否正確，清除 $HOME 下的證書文件。
   - `dd` 后運行 `sudo partprobe` 讓 Linux 刷新設備，之後就可以找到那個 AMI 的 Source volume.
   - 用 `sudo e2label <source device>` 檢查 volume 的 label 是否與 grub 裏設置的一致。
     (不出意外，是不會錯的)
   - 在這裡還可以刪除 $HOME 下的證書文件。以防止安全漏洞。
5. 把該 `dd` 還原的 volume detach。
6. 從該 Volume 生成一個新的 EBS Snapshot
7. 從這個新的 EBS Snapshot 生成新的 AMI (注意 Virtualization 選 hvm)
8. 最後測試這個新的 AMI 可以被 Launch

- 一切結束后把用到的臨時 Volumes, Instances 都清理掉。

# Windows AMI 的遷移

- AMI 導出到 file 
  與 Linux 的導出方法一致,只是 Windows OS 通常更大。注意分配足夠的空間。

- 在 AWS China 將 image 文件做成 AMI
  前半部分與只是 Windows 最好用 Instances Save AMI 的方法。以免不能啓動。
1. 啓動一個 Linux Instance 在 AWS China   
2. 創建一個足夠大小的 EBS Volume, attache 到 Linux Instance 上。
   (這個大小取決於 Source AMI Linux Volume 大小，最好和他一樣大。不能比它小)
3. 在 China 這個 Linux instance 上用 `dd` 把 image 文件寫回剛才 mount 的設備上。
5. 把該 `dd` 還原的 volume detach。
6. 啓動一個新的 Windows Instance。將其 Stop 並把 root volume detach 掉。
7. 把剛才 `dd` 出來的 volume attach 到這個新的 Windows 上成爲 Root device。
   (要選之前 root device 一樣的設備名比如: `/dev/sda1` ) 
8. 重新 Start 這個 Windows Instance。 (這時用 RDP 登上去檢查一下，應該就是 copy 過來的那個 Windows OS 了)
9. 從這個 Windows Instance Save 一個 AMI 出來。

- 同樣一切結束后把用到的臨時 Volumes, Instances 都清理掉。

----

# 最後
願有朝一日 "結界" 不存，則吾輩無需為此等雜務去浪費時間。

