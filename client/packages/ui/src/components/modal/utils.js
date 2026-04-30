/**
 * modal/utils.js
 * 所有模板共享的纯工具函数，无任何业务依赖
 */

/** HTML 属性值转义 */
export function esc(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/'/g, '&#39;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/** 根据字段类型返回 badge CSS 类名 */
export function attrBadgeCls(type) {
    return { string: 'badge-str', number: 'badge-num',
             boolean: 'badge-bool', date: 'badge-date' }[type] ?? 'badge-str';
}

/** 根据字段类型返回图标字符 */
export function attrTypeIcon(type) {
    return { string: 'T', number: '#', boolean: '⊙', date: '▦' }[type] ?? '?';
}

/** 格式化单元格显示值 */
export function attrFmtVal(val, type) {
    if (val === null || val === undefined || val === '')
        return '<span class="text-slate-300 select-none">—</span>';
    if (type === 'boolean') return val ? '✅' : '❌';
    if (type === 'date') {
        try { return new Date(val).toLocaleDateString('zh-CN'); } catch { return String(val); }
    }
    return String(val);
}

/** 渲染通用下拉选择框 <option> 列表 */
export function renderSelectOptions(rasters) {
    if (!rasters || rasters.length === 0)
        return '<option value="">请先上传影像</option>';
    return rasters.map(r =>
        `<option value="${r.index_id}">${r.file_name} (${r.bands} 波段)</option>`
    ).join('');
}

/** 渲染通用加载等待状态 */
export function renderActionLoading(message = '正在执行算法...') {
    return `
        <div class="flex flex-col items-center justify-center py-12">
            <div class="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-xs font-bold text-slate-600">${message}</p>
            <p class="text-[9px] text-slate-400 mt-2 tracking-widest uppercase">请稍候，服务器正在处理数据</p>
        </div>
    `;
}
