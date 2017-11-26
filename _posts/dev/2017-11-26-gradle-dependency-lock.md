---
layout: post
title: "Gradle dependency lock"
description: ""
category: dev
tags: [tips, dev, java]
---
{% include JB/setup %}

记录一下前一段厂里实际遇到的一连串关于 Gradle Java 工程打包是遇到的问题。

## 问题
当时的问题大致是这样的：厂里的一个小工程用到了 Selenium + Firefox WebDriver。
在 Release 时，用的是 Selenium version 3.2 。所以相应的 Firefox WebDriver 也用了
3.2 对应的环境。但是新的 CI Building 出来的包在 Firefox WebDriver 测试时会报 
`java.lang.NoClassDefFoundError` 的 Exception 。

## 问题原因
调查后发现问题原因是，新的 CI build 打包时自动把 Selenium 的版本更新到了最新。
然而 Firefox WebDriver 依旧在使用 version 3.2 对应的版本。导致 WebDriver 在调用
的 Selenium 方法已经在新版本的 Selenium 中移除。

---

## 解决的方式和一些插曲

### dependency lock

Gradle 打包时可以用 dependency lock 的 plugin 来锁定依赖库的版本。     
只需要用 plugin `nebula.dependency-lock` 生成 `dependencies.lock` 。
以后 gradle build task 时就会严格依照 `dependencies.lock` 中规定的版本来打包。
- Gradle Plugin:`nebula.dependency-lock` 
  [plugin page](https://plugins.gradle.org/plugin/nebula.dependency-lock)

## 插曲
加上一试本地 build 果然都好了，开心提交了 change 准备做新 build 测一下就可以回家了。
但是 CI 做出的 build 依旧有问题。

为了调查 CI 机器上的 build 我有为此加入了 Gradle Project report plugin。
用来输出 project 所有 dependencies 信息。
- Project report plugin 是 Gradle 自带的: [grdale doc](https://docs.gradle.org/current/userguide/project_reports_plugin.html)

调查发现原来 CI 所用的 Gradle version 和我本地不一样，导致 `dependencies.lock` 无效。
于是换到了 CI 环境用的 Gradle version 重新生成 `dependencies.lock` 总算 CI 的输出也正确了。

---

## 关于 gradlew

如果之前的 project 用了 gradlew 是可以避免后面碰到的 CI 机器与本地机器上的 gradle version 差异的问题的。

一直没有搞是因为，所用的 git repository 有一个不提交 binary file 的规则。想要设置例外，必须麻烦管理员。


## 总结
- 以后的 Java Gradle project 要注意加上 dependencies lock 。
  可以防止每次 release 时的差异。
- 为了不麻烦别人，问题会积累。比如，不麻烦管理员开放权限，所有没有 gradlew ；
  不麻烦 dba 升级 db 自己加字段解决等等；不麻烦 DevOps 部署新服务，
  自己用原有进程 forke  一个自己管理的子进程。多个 release 之后连自己也会掉入自己挖的坑。 

