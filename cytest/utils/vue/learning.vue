<script setup>
import { ref } from 'vue';

// --- 1. 定义响应式数据 ---

// 定义一个数组，用来存日志对象
// 泛型/对象结构: { id: 1, time: '10:00:01', level: 'INFO', msg: 'xxx' }
const logs = ref([]); 

// 只是为了生成自增 ID 用的计数器
let nextId = 1;

// --- 2. 定义方法 ---

// 模拟产生一条新日志
const addLog = () => {
    const now = new Date().toLocaleTimeString();
    
    // 随机搞个级别，模拟真实场景
    const levels = ['INFO', 'INFO', 'WARN', 'ERROR'];
    const randomLevel = levels[Math.floor(Math.random() * levels.length)];
    
    // 往数组头部添加 (unshift)，这样最新的在最上面
    // 注意：操作 ref 必须加 .value
    logs.value.unshift({
        id: nextId++,
        time: now,
        level: randomLevel,
        msg: `执行测试用例 TC_${Math.floor(Math.random() * 1000)}...`
    });
};

// 清空日志
const clearLogs = () => {
    logs.value = []; // 直接赋值空数组，Vue 会检测到变化并更新界面
};
</script>

<template>
  <div class="log-container">
    <h2>📊 自动化测试实时日志</h2>

    <div class="controls">
      <button @click="addLog" class="btn add">➕ 模拟产生日志</button>
      <button @click="clearLogs" class="btn clear">🗑️ 清空</button>
      
      <span v-show="logs.length > 0" class="count">
        当前日志: {{ logs.length }} 条
      </span>
    </div>

    <div class="log-window">
      
      <div v-if="logs.length === 0" class="empty-state">
        😴 等待测试运行... (暂无数据)
      </div>

      <ul v-else>
        <li v-for="item in logs" :key="item.id" class="log-item">
          <span class="time">[{{ item.time }}]</span>
          
          <span :class="['tag', item.level]">
            {{ item.level }}
          </span>
          
          <span :class="{ 'error-msg': item.level === 'ERROR' }">
            {{ item.msg }}
          </span>
        </li>
      </ul>
      
    </div>
  </div>
</template>

<style scoped>
/* 简单的 CSS 美化，不用太纠结，看懂结构即可 */
.log-container {
  padding: 20px;
  max-width: 600px;
  margin: 0 auto;
  font-family: 'Consolas', monospace; /* 代码风格字体 */
}

.controls {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.btn {
  padding: 8px 15px;
  cursor: pointer;
  border: none;
  border-radius: 4px;
  font-weight: bold;
}
.add { background-color: #42b983; color: white; }
.clear { background-color: #ff6b6b; color: white; }
.count { color: #666; font-size: 0.9em; }

.log-window {
  background-color: #1e1e1e; /* 黑色背景 */
  color: #d4d4d4;
  padding: 15px;
  border-radius: 8px;
  min-height: 200px;
  max-height: 400px;
  overflow-y: auto; /* 内容多了可以滚动 */
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}

.empty-state {
  color: #666;
  text-align: center;
  margin-top: 50px;
}

ul {
  list-style: none; /* 去掉前面的圆点 */
  padding: 0;
  margin: 0;
}

.log-item {
  padding: 5px 0;
  border-bottom: 1px solid #333;
}

.time { color: #888; margin-right: 10px; font-size: 0.85em; }

.tag {
  font-size: 0.8em;
  padding: 2px 5px;
  border-radius: 3px;
  margin-right: 8px;
  color: white;
}
.tag.INFO { background-color: #2196F3; }
.tag.WARN { background-color: #FFC107; color: black; }
.tag.ERROR { background-color: #F44336; }

.error-msg {
  color: #ff6b6b;
  font-weight: bold;
  text-decoration: underline;
}
</style>