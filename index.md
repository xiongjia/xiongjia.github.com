---
layout: page
title: Home
tagline: Supporting tagline
---
{% include JB/setup %}

## About

- Github: [https://github.com/xiongjia](https://github.com/xiongjia){:target="_blank"} 
- Mail: <a href="mailto:lexiongjia@gmail.com">lexiongjia@gmail.com</a> 

## Posts

<ul class="posts">
  {% for post in site.posts %}
    <li>
        <span>{{ post.date | date: "%m-%d %Y" }}</span> &raquo;
        <a href="{{ BASE_PATH }}{{ post.url }}">{{ post.title }}</a> &nbsp;
        <span>({{ post.categories }}) </span> &nbsp;
    </li>
  {% endfor %}
</ul>
