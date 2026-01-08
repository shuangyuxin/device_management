// 通用JavaScript功能

// 页面加载完成后的初始化
$(document).ready(function() {
    // 自动关闭警告框
    $('.alert').delay(3000).fadeOut('slow');
    
    // 表单验证
    $('form').on('submit', function(e) {
        const requiredFields = $(this).find('[required]');
        let valid = true;
        
        requiredFields.each(function() {
            if (!$(this).val().trim()) {
                valid = false;
                $(this).addClass('is-invalid');
            } else {
                $(this).removeClass('is-invalid');
            }
        });
        
        if (!valid) {
            e.preventDefault();
            alert('请填写所有必填字段！');
        }
    });
    
    // 移除无效样式当用户开始输入时
    $('input, textarea, select').on('input change', function() {
        if ($(this).val().trim()) {
            $(this).removeClass('is-invalid');
        }
    });
    
    // 确认删除操作
    $('.confirm-delete').on('click', function(e) {
        if (!confirm('确定要删除吗？此操作不可撤销！')) {
            e.preventDefault();
        }
    });
    
    // 工具提示
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // 弹出框
    $('[data-bs-toggle="popover"]').popover();
});

// 日期格式化
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

// 导出为Excel
function exportToExcel(tableId, filename) {
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tr');
    let csv = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            // 移除按钮等内容
            if (cols[j].querySelector('button, a')) {
                continue;
            }
            row.push('"' + cols[j].innerText.replace(/"/g, '""') + '"');
        }
        
        csv.push(row.join(','));
    }
    
    const csvString = csv.join('\n');
    const blob = new Blob(['\uFEFF' + csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (navigator.msSaveBlob) {
        navigator.msSaveBlob(blob, filename);
    } else {
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

// 复制到剪贴板
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        alert('已复制到剪贴板');
    }, function(err) {
        console.error('复制失败: ', err);
        alert('复制失败，请手动复制');
    });
}

// AJAX请求包装器
function ajaxRequest(url, method, data, successCallback, errorCallback) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    fetch(url, options)
        .then(response => response.json())
        .then(successCallback)
        .catch(error => {
            console.error('请求失败:', error);
            if (errorCallback) errorCallback(error);
            else alert('操作失败，请重试');
        });
}

// 设备管理相关函数
function checkCalibrationStatus(calibrationDate) {
    const today = new Date();
    const calDate = new Date(calibrationDate);
    const diffTime = calDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays <= 30) {
        return { status: 'danger', text: '即将到期' };
    } else if (diffDays <= 90) {
        return { status: 'warning', text: '即将到期' };
    } else {
        return { status: 'success', text: '正常' };
    }
}