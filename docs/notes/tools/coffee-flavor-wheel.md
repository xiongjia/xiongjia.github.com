---
icon: material/coffee
hide:
  - tags
---

# ☕ 咖啡风味轮

交互式 SCA 咖啡风味轮：悬停高亮同族风味、点击锁定详情、追溯完整风味路径。风味数据内嵌于页面代码，纯前端渲染，零依赖、无需联网。

______________________________________________________________________

<div class="cfw-wrap">
  <svg class="cfw-svg" viewBox="0 0 600 600" id="cfw-wheel" role="img" aria-label="咖啡风味轮"></svg>
  <div class="cfw-info" id="cfw-info">
    <div class="cfw-info-title" id="cfw-info-title">将鼠标悬停在风味区域上</div>
    <div class="cfw-info-desc" id="cfw-info-desc">
      从中心向外探索：先感知大类（花香、水果等），再逐步细化到具体风味。
      悬停高亮同族风味，点击锁定选择，点击中心圆或空白处取消。
    </div>
    <div class="cfw-info-path" id="cfw-info-path"></div>
  </div>
  <div class="cfw-legend" id="cfw-legend"></div>
  <div class="cfw-hint">💡 悬停高亮同族风味 · 点击锁定详情 · 点击中心圆取消</div>
</div>

<script>
(function () {
  "use strict";

  // ==================== 常量 ====================
  var CX = 300, CY = 300;   // 圆心坐标
  var INNER_R = 45;         // 中心圆半径
  var OUTER_R = 280;        // 最外圈半径
  var LABEL_FONT_PX = 11;   // 标签字号（对应 CSS .cfw-label font-size）

  // ==================== 数据层 ====================
  var flavorData = {
    name: "风味",
    color: "#f5f0eb",
    children: [
      {
        name: "花香",
        color: "#F8BBD0",
        children: [
          { name: "茉莉", color: "#F48FB1" },
          { name: "玫瑰", color: "#F06292" },
          { name: "薰衣草", color: "#EC407A" },
          { name: "洋甘菊", color: "#D81B60" },
          { name: "橙花", color: "#C2185B" },
          { name: "木槿", color: "#AD1457" }
        ]
      },
      {
        name: "水果",
        color: "#FFCC80",
        children: [
          {
            name: "浆果",
            color: "#FFB74D",
            children: [
              { name: "草莓", color: "#FFA726" },
              { name: "覆盆子", color: "#FB8C00" },
              { name: "蓝莓", color: "#F57C00" },
              { name: "黑莓", color: "#EF6C00" }
            ]
          },
          {
            name: "干果",
            color: "#FF9800",
            children: [
              { name: "葡萄干", color: "#F57C00" },
              { name: "西梅", color: "#E65100" },
              { name: "椰枣", color: "#BF360C" }
            ]
          },
          {
            name: "柑橘",
            color: "#FFD54F",
            children: [
              { name: "柠檬", color: "#FFC107" },
              { name: "橙子", color: "#FFB300" },
              { name: "柚子", color: "#FFA000" },
              { name: "莱姆", color: "#FF8F00" }
            ]
          },
          {
            name: "其他水果",
            color: "#FFAB91",
            children: [
              { name: "苹果", color: "#FF8A65" },
              { name: "梨", color: "#FF7043" },
              { name: "葡萄", color: "#FF5722" },
              { name: "桃子", color: "#E64A19" },
              { name: "菠萝", color: "#D84315" },
              { name: "芒果", color: "#BF360C" }
            ]
          }
        ]
      },
      {
        name: "糖类/焦糖",
        color: "#D7CCC8",
        children: [
          { name: "蜂蜜", color: "#BCAAA4" },
          { name: "焦糖", color: "#A1887F" },
          { name: "枫糖", color: "#8D6E63" },
          { name: "红糖", color: "#795548" },
          { name: "香草", color: "#6D4C41" },
          { name: "太妃糖", color: "#5D4037" }
        ]
      },
      {
        name: "坚果/可可",
        color: "#A1887F",
        children: [
          { name: "杏仁", color: "#8D6E63" },
          { name: "榛子", color: "#795548" },
          { name: "花生", color: "#6D4C41" },
          { name: "可可", color: "#5D4037" },
          { name: "黑巧克力", color: "#4E342E" },
          { name: "摩卡", color: "#3E2723" }
        ]
      },
      {
        name: "香料",
        color: "#C5CAE9",
        children: [
          { name: "肉桂", color: "#9FA8DA" },
          { name: "丁香", color: "#7986CB" },
          { name: "胡椒", color: "#5C6BC0" },
          { name: "豆蔻", color: "#3F51B5" },
          { name: "姜", color: "#303F9F" }
        ]
      },
      {
        name: "烘焙",
        color: "#B0BEC5",
        children: [
          { name: "吐司", color: "#90A4AE" },
          { name: "烘焙咖啡", color: "#78909C" },
          { name: "烟熏", color: "#607D8B" },
          { name: "焦糊", color: "#546E7A" },
          { name: "烟草", color: "#455A64" },
          { name: "灰烬", color: "#37474F" }
        ]
      },
      {
        name: "谷物/植物",
        color: "#C8E6C9",
        children: [
          { name: "谷物", color: "#A5D6A7" },
          { name: "麦芽", color: "#81C784" },
          { name: "稻草", color: "#66BB6A" },
          { name: "青草", color: "#4CAF50" },
          { name: "木质", color: "#43A047" },
          { name: "树皮", color: "#388E3C" }
        ]
      },
      {
        name: "化学/瑕疵",
        color: "#CFD8DC",
        children: [
          { name: "橡胶", color: "#B0BEC5" },
          { name: "皮革", color: "#90A4AE" },
          { name: "泥土", color: "#78909C" },
          { name: "霉味", color: "#607D8B" },
          { name: "发酵", color: "#546E7A" },
          { name: "酚类", color: "#455A64" }
        ]
      }
    ]
  };

  // ==================== 预处理 ====================
  // flatten 构建完整的扁平树：每个节点都带 id/depth/parentId，
  // children 指向扁平后的子节点（而非原始数据），供角度分配与渲染统一使用
  var allNodes = [];   // 扁平化后的节点数组
  var byId = {};       // id -> node 索引
  var nextId = 0;

  function flatten(node, depth, parentId) {
    var flat = {
      id: nextId++,
      name: node.name,
      color: node.color,
      depth: depth,
      parentId: parentId,
      children: []
    };
    allNodes.push(flat);
    byId[flat.id] = flat;
    var kids = node.children || [];
    for (var i = 0; i < kids.length; i++) {
      flat.children.push(flatten(kids[i], depth + 1, flat.id));
    }
    return flat;
  }

  var root = flatten(flavorData, 0, null);

  // 环宽按每个大类的子树层数独立计算，保证所有叶子都延伸到最外缘。
  // （全局 maxDepth 会让只有 2 层的大类叶子停在中间环，外圈留下大片空白）
  function subtreeLevels(node) {
    if (node.children.length === 0) return 1;
    var max = 0;
    for (var i = 0; i < node.children.length; i++) {
      var l = subtreeLevels(node.children[i]);
      if (l > max) max = l;
    }
    return max + 1;
  }

  function assignRingWidth(node, rw) {
    node.ringWidth = rw;
    for (var i = 0; i < node.children.length; i++) assignRingWidth(node.children[i], rw);
  }

  for (var c = 0; c < root.children.length; c++) {
    var cat = root.children[c];
    assignRingWidth(cat, (OUTER_R - INNER_R) / subtreeLevels(cat));
  }

  function assignAngles(node, startAngle, endAngle) {
    node.startAngle = startAngle;
    node.endAngle = endAngle;
    if (node.children.length > 0) {
      var span = (endAngle - startAngle) / node.children.length;
      var current = startAngle;
      for (var i = 0; i < node.children.length; i++) {
        assignAngles(node.children[i], current, current + span);
        current += span;
      }
    }
  }
  assignAngles(root, 0, Math.PI * 2);

  // ==================== 渲染层 ====================
  var svg = document.getElementById("cfw-wheel");
  var SVG_NS = "http://www.w3.org/2000/svg";
  var lockedNode = null;

  function arcPath(sa, ea, rIn, rOut) {
    var x1 = CX + rIn * Math.cos(sa), y1 = CY + rIn * Math.sin(sa);
    var x2 = CX + rOut * Math.cos(sa), y2 = CY + rOut * Math.sin(sa);
    var x3 = CX + rOut * Math.cos(ea), y3 = CY + rOut * Math.sin(ea);
    var x4 = CX + rIn * Math.cos(ea), y4 = CY + rIn * Math.sin(ea);
    var largeArc = (ea - sa) > Math.PI ? 1 : 0;
    return "M " + x1 + " " + y1 +
      " L " + x2 + " " + y2 +
      " A " + rOut + " " + rOut + " 0 " + largeArc + " 1 " + x3 + " " + y3 +
      " L " + x4 + " " + y4 +
      " A " + rIn + " " + rIn + " 0 " + largeArc + " 0 " + x1 + " " + y1 + " Z";
  }

  function drawSector(node) {
    if (node.depth === 0) return;
    var rw = node.ringWidth;
    var r1 = INNER_R + (node.depth - 1) * rw;
    var r2 = INNER_R + node.depth * rw - 2;
    var midAngle = (node.startAngle + node.endAngle) / 2;

    var path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", arcPath(node.startAngle, node.endAngle, r1, r2));
    path.setAttribute("fill", node.color || "#ccc");
    path.setAttribute("class", "cfw-sector");
    path.setAttribute("data-id", node.id);

    var labelR = (r1 + r2) / 2;

    path.addEventListener("mouseenter", function () { if (!lockedNode) highlight(node, false); });
    path.addEventListener("mouseleave", function () { if (!lockedNode) clearHighlight(); });
    path.addEventListener("click", function (e) { e.stopPropagation(); toggleLock(node); });

    svg.appendChild(path);

    // 过窄的扇区不创建文字标签：弧长 = span × labelR，小于字号即与相邻
    // 径向标签重叠（悬停/点击仍可在信息面板看到名称）
    if ((node.endAngle - node.startAngle) * labelR >= LABEL_FONT_PX) {
      var labelX = CX + labelR * Math.cos(midAngle);
      var labelY = CY + labelR * Math.sin(midAngle);

      var text = document.createElementNS(SVG_NS, "text");
      text.setAttribute("x", labelX);
      text.setAttribute("y", labelY);
      text.setAttribute("class", "cfw-label");
      text.textContent = node.name;

      var angleDeg = midAngle * 180 / Math.PI;
      // 左半轮翻转 180° 保持文字正立可读；labelRotate 即最终旋转角（度数）
      var labelRotate = (angleDeg > 90 && angleDeg < 270) ? angleDeg + 180 : angleDeg;
      if (node.depth >= 3 || (node.endAngle - node.startAngle) < 0.25) {
        // 沿径向排列（文字顺着半径方向），窄扇区弧宽有限、径向空间充足
        text.setAttribute("transform", "rotate(" + labelRotate + ", " + labelX + ", " + labelY + ")");
      }

      svg.appendChild(text);
    }
  }

  function drawAll(node) {
    drawSector(node);
    for (var i = 0; i < node.children.length; i++) drawAll(node.children[i]);
  }

  // 中心圆
  var center = document.createElementNS(SVG_NS, "circle");
  center.setAttribute("cx", CX);
  center.setAttribute("cy", CY);
  center.setAttribute("r", INNER_R - 5);
  center.setAttribute("class", "cfw-center");
  center.addEventListener("click", function () {
    lockedNode = null;
    clearHighlight();
    updateInfo(null);
  });
  svg.appendChild(center);

  var centerText = document.createElementNS(SVG_NS, "text");
  centerText.setAttribute("x", CX);
  centerText.setAttribute("y", CY);
  centerText.setAttribute("class", "cfw-center-text");
  centerText.textContent = "风味";
  svg.appendChild(centerText);

  drawAll(root);

  // ==================== 交互层 ====================
  function collectIds(node, target) {
    target[node.id] = true;
    for (var i = 0; i < node.children.length; i++) collectIds(node.children[i], target);
  }

  function highlight(node, isLocked) {
    var sectors = svg.querySelectorAll(".cfw-sector");
    var targetIds = {};
    collectIds(node, targetIds);

    var cur = node;
    while (cur.parentId !== null) {
      cur = byId[cur.parentId];
      targetIds[cur.id] = true;
    }

    for (var i = 0; i < sectors.length; i++) {
      var sid = sectors[i].getAttribute("data-id");
      if (!targetIds[sid]) sectors[i].classList.add("cfw-dimmed");
      else sectors[i].classList.remove("cfw-dimmed");
    }
    updateInfo(node, isLocked);
  }

  function clearHighlight() {
    var sectors = svg.querySelectorAll(".cfw-sector");
    for (var i = 0; i < sectors.length; i++) sectors[i].classList.remove("cfw-dimmed");
    updateInfo(null);
  }

  function toggleLock(node) {
    if (lockedNode && lockedNode.id === node.id) {
      lockedNode = null;
      clearHighlight();
    } else {
      lockedNode = node;
      highlight(node, true);
    }
  }

  // ==================== UI 层 ====================
  var descriptions = {
    "花香": "由咖啡中的挥发性芳香化合物产生，通常在浅烘焙、高海拔豆中最为明显。",
    "水果": "酶促反应产物，常见于日晒处理或蜜处理的咖啡中，是精品咖啡的核心魅力。",
    "浆果": "红色/深色水果类风味，通常与咖啡中的酯类和醛类物质相关。",
    "干果": "脱水水果的甜香，常出现在陈年豆或特定处理法中。",
    "柑橘": "明亮的酸质与清新香气，是埃塞俄比亚、肯尼亚等产地咖啡的典型特征。",
    "其他水果": "苹果、梨、葡萄等温带水果风味，常见于中美洲和哥伦比亚咖啡。",
    "糖类/焦糖": "焦糖化反应产物，随烘焙度加深而增强，从浅烘的蜂蜜到深烘的焦糖。",
    "坚果/可可": "中深烘焙的典型风味，由美拉德反应产生，给人温暖醇厚的感觉。",
    "香料": "常与特定产地相关，如印尼曼特宁的肉桂感、也门咖啡的香料调。",
    "烘焙": "烘焙过程中产生的干馏化产物，深烘豆更为明显。",
    "谷物/植物": "种植阶段酶促反应的产物，常见于浅烘或中浅烘咖啡。",
    "化学/瑕疵": "负面风味或瑕疵味，可能来自处理不当、储存问题或过度发酵。"
  };

  function updateInfo(node, isLocked) {
    var title = document.getElementById("cfw-info-title");
    var desc = document.getElementById("cfw-info-desc");
    var pathEl = document.getElementById("cfw-info-path");

    if (!node) {
      title.textContent = "将鼠标悬停在风味区域上";
      desc.textContent = "从中心向外探索：先感知大类（花香、水果等），再逐步细化到具体风味。悬停高亮同族风味，点击锁定选择，点击中心圆或空白处取消。";
      pathEl.textContent = "";
      return;
    }

    title.textContent = (isLocked ? "🔒 " : "") + node.name;
    desc.textContent = descriptions[node.name] ||
      (node.parentId !== null ? (descriptions[byId[node.parentId].name] || "") : "") ||
      "咖啡风味轮中的具体风味描述，帮助杯测师精准定位感官体验。";

    var parts = [];
    var cur = node;
    while (cur) {
      parts.unshift(cur.name);
      cur = cur.parentId !== null ? byId[cur.parentId] : null;
    }
    pathEl.textContent = "路径：" + parts.join(" → ");
  }

  // 图例
  var legend = document.getElementById("cfw-legend");
  var rootChildren = root.children;
  for (var i = 0; i < rootChildren.length; i++) {
    var item = document.createElement("div");
    item.className = "cfw-legend-item";
    var dot = document.createElement("span");
    dot.className = "cfw-legend-dot";
    dot.style.background = rootChildren[i].color;
    var name = document.createElement("span");
    name.textContent = rootChildren[i].name;
    item.appendChild(dot);
    item.appendChild(name);
    legend.appendChild(item);
  }

  // 点击空白处取消锁定
  svg.addEventListener("click", function () {
    if (lockedNode) {
      lockedNode = null;
      clearHighlight();
      updateInfo(null);
    }
  });
})();
</script>

______________________________________________________________________

## 📝 使用说明

| 操作                    | 说明                                                       |
| ----------------------- | ---------------------------------------------------------- |
| **悬停**                | 高亮同族风味（当前节点 + 其祖先 + 所有后代），其余区域淡化 |
| **点击**                | 锁定当前选择，信息面板显示完整风味路径与描述               |
| **再次点击**            | 解锁当前选择                                               |
| **点击中心圆 / 空白处** | 取消锁定，恢复全量显示                                     |

## 🧭 探索逻辑

- 风味轮为**同心圆结构**：中心为「风味」，向外依次为**大类**（花香、水果、糖类/焦糖…）→ **子类**（浆果、干果、柑橘…）→ **具体风味**（草莓、柠檬、葡萄干…）
- 遵循 SCA（精品咖啡协会）风味轮的认知逻辑：**先整体后细节**，从大类逐步细化到具体风味
- 大类色系与图例一一对应，帮助快速定位

> 风味数据内嵌于页面（基于 SCA Coffee Taster's Flavor Wheel 精简结构），纯前端 SVG 渲染，无外部请求、不存储任何用户数据。
