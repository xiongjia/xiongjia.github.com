---
layout: post
title: "Node.js 中的 Database 實踐/練習"
description: ""
category: dev
tags: [dev, gist, scratch, Node.js, database, liquibase, Knexjs, Bookshelfjs]
---
{% include JB/setup %}

記錄一下幾個在實踐中用到的與 Node.js & Database 相關的 Tools / Frameworks。   
主要用到以下幾個:   

- [Knexjs](http://knexjs.org/){:target="_blank"} - A SQL query builder for node.js. 
- [Bookshelfjs](http://bookshelfjs.org/){:target="_blank"} - A javascript ORM for node.js.
- [Liquibase](http://www.liquibase.org/){:target="_blank"} - A Refactor tool.

3者之間的關係如下圖:

![database]({{ site.url }}/assets/res/img/dev-node-db-01.png)

## Bookshelfjs
[Bookshelfjs](http://bookshelfjs.org/){:target="_blank"} 是一個 node.js 實現的 Database ORM。 

- Bookshelfjs 類似與 [Backbone.js](http://backbonejs.org/){:target="_blank"} 的風格。提供 Model, Collection 的概念。
- 使用了 [bluebird](https://github.com/petkaantonov/bluebird){:target="_blank"} 
  的 promises 實現。來幫助異步操作。
- 使用 Knexjs 做為 Database query builder 和 connection 管理。

Bookshelfjs 實踐的 Gist: [https://gist.github.com/xiongjia/eeaf9d0d7571b4d15f3f](https://gist.github.com/xiongjia/eeaf9d0d7571b4d15f3f){:target="_blank"}

- 在 Gist 中 README 中描述了 Sample 的用法和 Database 的 Schema
- 在 `orm.js` 定義了 Database 的 Objects.

## Knexjs
[Knexjs](http://knexjs.org/){:target="_blank"} 是一個 node.js 實現 SQL query builder 。

- 目前的版本支持 Postgres, MySQL, MariaDB and SQLite3 
- 使用了 [bluebird](https://github.com/petkaantonov/bluebird){:target="_blank"}
  的 promises 實現。來幫助異步操作。
- 使用 [generic pool](https://github.com/bookshelf/generic-pool-redux){:target="_blank"} 
  來做 Database connection pool 的管理。
- 支持 Database transaction; Schema builder 

Knexjs 實踐的 Gist: [https://gist.github.com/xiongjia/85df587ce3535d1c6151](https://gist.github.com/xiongjia/85df587ce3535d1c6151){:target="_blank"} 

- 在 Gist 中 README 中描述了 Sample 的用法和 Database 的 Schema

## Liquibase
[Liquibase](http://www.liquibase.org/){:target="_blank"} 是一個在開發過程中使用的 Database tool。
可以在通過它的 Data change log 來管理開發過程中數據庫的變化過程。也可以做 rollback; update; migrate 等操作。

Liquibase 實踐的 Gist: [https://gist.github.com/xiongjia/455c27bb728325542f66](https://gist.github.com/xiongjia/455c27bb728325542f66){:target="_blank"}

- 在 Gist 中 README 中描述了 Sample 的用法和 Database 的 Schema
- Liquibase 是基於 Java 的，必須正確配置對應的 JDBC Driver。具體參看 Gist 中的 README。

----

# 最後
通過 ORM 訪問數據庫的優劣:

## 好處:

- 同一份代碼工作在不同的數據庫。(比如: 開發環境用 SQLite3, 生產環境用 Postgres)
- 部分避免 SQL Injection attacks。
- 有利於代碼結構和可持續性開發。

## 壞處:

- 增加學習成本。 (比如: 必須理解 Backbone Model, Collection 的工作原理; promises 的風格 等)
- 目前 Knexjs 支持的數據庫較少，只有 Postgres, MySQL, MariaDB and SQLite3 
- 喪失部分數據庫特性，可能影響性能。


