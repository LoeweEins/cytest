// report 的交互脚本

// 实现三个功能：
// 1. 切换测试用例显示模式，精简/详细
// 2. 定位到上一个/下一个错误
// 3. 折叠/展开测试用例文件夹

var FOLDER_ALL_CASES = false //是否为精简模式的标记
var ERROR_INFOS = [];  // 错误信息列表
var current_error_idx = -1;

// 页面加载后执行的函数
// 等到 HTML、CSS、图片都加载完 以后，再执行回调函数
// 这样可以确保页面元素 .folder_header、.error-info 都存在
window.addEventListener("load", function(){
   
    // 选出页面上所有 .folder_header 
    let folderHeaderEles = document.querySelectorAll(".folder_header");
    // 为每个 .folder_header 绑定点击事件处理
    folderHeaderEles.forEach(function(ele) {
        ele.addEventListener("click", function(event) {
        let fb = event.target.closest('.folder_header').nextElementSibling; // 父节点往上找 .folder_header，再找其兄弟元素
        
        // 切换显示/隐藏，toggle
        fb.style.display = fb.style.display === 'none' ? 'block' : 'none';
        });
    });

//--------------------------------------------------------------------

    // 找到所有的错误信息对象
    ERROR_INFOS = document.querySelectorAll(".error-info");
});


// 切换用例 精简/详细
function toggle_folder_all_cases(){
    let eles = document.querySelectorAll(".folder_body"); // 选出所有 .folder_body 
    
    FOLDER_ALL_CASES = !FOLDER_ALL_CASES; // 更新显示文字 detail/summary
    document.getElementById('display_mode').innerHTML = FOLDER_ALL_CASES? "Detail" : "Summary"

    // 根据模式，逐个 .folder_body 显示/隐藏
    for (const ele of eles){
        ele.style.display =  FOLDER_ALL_CASES? "none": "block"
    }
    
}

//--------------------------------------------------------------------

function previous_error(){
    // 查找错误必须是详细模式
    if (FOLDER_ALL_CASES)
        toggle_folder_all_cases()

    current_error_idx -= 1; 
    if (current_error_idx<0)
        current_error_idx = 0

    
    let error = ERROR_INFOS[current_error_idx];

    // 使用浏览器提供的方法
    error.scrollIntoView({behavior: "smooth", block: "center", inline: "start"});

    
}


function next_error(){
    
    // 查找错误必须是详细模式
    if (FOLDER_ALL_CASES)
        toggle_folder_all_cases()

    current_error_idx += 1;
    if (current_error_idx > ERROR_INFOS.length-1)
        current_error_idx = ERROR_INFOS.length-1

    let error = ERROR_INFOS[current_error_idx];

    error.scrollIntoView({behavior: "smooth", block: "center", inline: "start"});
    
}
/*所有监听点击操作都是通过：
*	HTML 上 onclick=xxx
*	或 JS 中 addEventListener('click', xxx)
*/

// .folder_header 的元素是动态生成的，必须等页面加载完后再绑定点击事件
// 而next_error、previous_error，直接通过onclick绑定在按钮上即可