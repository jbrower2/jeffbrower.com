---
title: Calendar Calculator
script: index.js
---

<label>
  Target Year:
  <input id="year" type="number" onchange="calc()" />
</label>

<div id="output"></div>

<script>
  document.getElementById("year").value = CURRENT_YEAR;
  calc();
</script>
