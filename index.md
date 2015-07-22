---
layout: page
title: Home
tagline: Supporting tagline
---
{% include JB/setup %}

## About

- Mail: <a href="mailto:lexiongjia@gmail.com">lexiongjia@gmail.com</a> 
- Github: [https://github.com/xiongjia](https://github.com/xiongjia)
- Wiki: [http://xj-labs.net/](http://xj-labs.net/) 
- G+: [https://plus.google.com/+XiongJiaLe](https://plus.google.com/+XiongJiaLe) 
 
## Posts

<ul class="posts">
  {% for post in site.posts %}
    <li><span>{{ post.date | date: "%m-%d %Y" }}</span> &raquo; <a href="{{ BASE_PATH }}{{ post.url }}">{{ post.title }}</a></li>
  {% endfor %}
</ul>


