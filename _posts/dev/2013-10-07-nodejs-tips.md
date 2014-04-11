---
layout: post
title: "node.js Tips"
description: ""
category: dev
tags: [dev, node.js, tips, node]
---
{% include JB/setup %}

并没有什么特别之处，只是记录一下开发中用到 NODEJS 用例，问题以及解决方式。  
此文组织混乱没有前后关系，每个章节都只是一个用例或问题。  
个人并不是 NODE.JS or JavaScript 的 Fan (不过我喜欢 UV)。目前用 Node 的原因，(1)工作需要 (2) 喜欢 UV。

## JSHint
Node.js 以 V8 的 Engine 为基础之一。(个人主观觉得 JS 是比较差的语言，但是他如此流行。以至于大家不得不学习，使用他。)  
JS 是一种弱类型语言，所以开始任何事情前请一定要设置好 JSHint ，帮助自己更好的使用 JS。  

1. 安装 JSHint  
 直接使用 `npm install jshint -g` 及可。  
2. 绑定编辑器   
 个人习惯是使用 VIM 。安装 vim syntastic plugin ( [https://github.com/scrooloose/syntastic](https://github.com/scrooloose/syntastic) ) 即可以。  
 其他编辑器应可以找到类似方式。比如 : Sublime Text，有钱人可以考虑用 Intellij。  
3. .jshintrc  
 定义你需要的规则在一个 .jshintrc 文件里，并将他应用于整个项目。所有的 Options 可以在 JSHint 的 document 里找到 ( [http://www.jshint.com/docs/options/](http://www.jshint.com/docs/options/) )。    
 另一种方法是用 Yeoman 创建一个 Node 工程。比如：`yo node` 。Yeoman 模板会创建一个预设的 .jshintrc 。相关问题可参考 Yeoman 官网 [http://yeoman.io/](http://yeoman.io/) 。  

## exports & module.exports  
经常看到 node 里写 `exports = module.exports = function() {}; ` 这样的代码。比较迷惑人的是 exprots 和 module.exports 的关系。  

这个在 NODEJS 的官网其实已经有解释。参考 Mdoule 的那个章节 http://nodejs.org/api/modules.html 里面有这个解释:  
Note that exports is a reference to module.exports making it suitable for augmentation only. If you are exporting a single item such as a constructor you will want to use module.exports directly instead.  

Node.js 为了实现 module 这个功能，会将你的 .js code 放入一个 function 的 closer 里。   
下面这个代码片摘自 node 的源代码：  

{% highlight javascript %}
  NativeModule.wrap = function(script) {
    return NativeModule.wrapper[0] + script + NativeModule.wrapper[1];
  };

  NativeModule.wrapper = [
    '(function (exports, require, module, __filename, __dirname) { ',
    '\n});'
  ];
{% endhighlight %}

里面的 'script' 就是对应 JS 脚本。 node 在使用它前在他前后加了2句，使他位于一个 Function 内。参数 exports 指向 module.exports 的 reference。所以当更新 module.exports 时也更新一下 exports 是一个比较好的习惯。


## node.js equivalent of python's if __name__ == '__main__'  
这个最早是在 Stackoverflow 上看到的：[http://stackoverflow.com/questions/4981891/node-js-equivalent-of-pythons-if-name-main](http://stackoverflow.com/questions/4981891/node-js-equivalent-of-pythons-if-name-main)   
node 的文档也有提到: [http://nodejs.org/api/modules.html#modules_accessing_the_main_module](http://nodejs.org/api/modules.html#modules_accessing_the_main_module)  

主要目的是，在写某些 node.js module 时可以写个 TestMain 测试一下，比如:

{% highlight javascript %} 
var testMain = function(){
    // your test code
};

if (require.main === module) {
    testMain();
}
{% endhighlight %}

这样 TestMain() 只有被 `node ./your.js` 执行时才会被运行，如同 Python 中 if __name__ == '__main__' 的效果。 

## Stream Module  
Stream 算是一个比较复杂的 node module 了。使用它的好处是可以把逻辑和 I/O 分离开来。比如：把协议解析写在 Stream 里。如果使用在网络上只需要把 socket pipe 过去，如果用在单元测试上直接 write 这个 stream 本身便可以测试。  

我写的一个 NODE Stream 协议解析测试放在了 Gist 上 [https://gist.github.com/xiongjia/6867670](https://gist.github.com/xiongjia/6867670)    

1. nsrv-protocol.js 是一个 steam 实现的 解析器。    
2. nclient.js 和 nsrv.js 是 2 个调用 sample 。    

除了官网上的 sample 和文档外，substack 写的 Steam handbook 包含有很多值得参考的信息 [https://github.com/substack/stream-handbook](https://github.com/substack/stream-handbook)



---  
(如果以后遇到值得记录的问题，应该会继续更新。)


