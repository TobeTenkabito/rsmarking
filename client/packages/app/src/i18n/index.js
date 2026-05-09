const STORAGE_KEY = 'rsmarking.ui.language';
const DEFAULT_LANGUAGE = 'zh';
const SUPPORTED_LANGUAGES = new Set(['zh', 'en']);

const messageCatalog = {
    zh: {
        'page.title': 'Agent RSMarking | 智能遥感系统 Pro',
        'nav.layerCounter': '已载入图层: {count}',
        'ui.loading.default': '处理中...',
        'ui.loading.serverHint': '请稍候，服务器正在处理数据',
        'clip.currentRaster': '当前影像：',
        'clip.noActiveRaster': '当前未加载任何栅格影像',
        'clip.useActiveLayer': '-- 使用当前激活图层 --',
        'clip.selectKnifeLayer': '-- 请选择裁剪刀图层 --',
        'clip.selectKnifeWarning': '请选择裁剪刀图层',
        'draw.none': '未选择工具',
        'draw.active': '绘制中：{tool}',
        'draw.tool.polygon': '多边形',
        'draw.tool.rectangle': '矩形',
        'draw.tool.circle': '圆形',
        'draw.tool.polyline': '线段',
        'draw.tool.marker': '标记点',
        'draw.tool.circlemarker': '采样点',
        'sidebar.raster.waiting': '等待数据载入...',
        'sidebar.raster.title': '影像资源 (Raster)',
        'sidebar.raster.import': '+ 导入',
        'sidebar.raster.bundle': '数据包: {id}',
        'sidebar.raster.members': '{count} 成员',
        'sidebar.raster.onMap': '地图中',
        'sidebar.raster.spectrumTitle': '光谱查询：点击后在地图上拾取像素',
        'sidebar.raster.attrTitle': '打开属性表',
        'sidebar.raster.removeTitle': '从工作站移除',
        'sidebar.vector.emptyProjects': '暂无标注项目',
        'sidebar.vector.title': '标注项目 (Vector)',
        'sidebar.vector.newProject': '+ 新建项目',
        'sidebar.vector.selectProject': '-- 选择标注项目 --',
        'sidebar.vector.projectTag': '项目: {name}',
        'sidebar.vector.importTitle': '导入 Shapefile（自动建图层）',
        'sidebar.vector.newLayerTitle': '新建空白图层',
        'sidebar.vector.emptyLayers': '尚未创建标注图层',
        'sidebar.vector.selectHint': '请先从下拉菜单选择项目',
        'sidebar.vector.currentEditing': '● 当前编辑图层',
        'sidebar.vector.clickToActivate': '点击激活编辑',
        'sidebar.vector.attrTitle': '打开属性表',
        'sidebar.vector.deleteTitle': '删除图层',
        'project.prompt.projectName': '请输入新矢量项目名称：',
        'project.prompt.projectDefault': '默认标注项目',
        'project.prompt.layerName': '请输入新标注图层名称：',
        'project.prompt.layerDefault': '建筑物标注',
        'project.alert.selectProjectFirst': '请先选择或创建一个矢量项目！',
        'project.alert.selectLayerFirst': '请先在左侧选择或创建一个目标标注图层',
        'project.confirm.deleteFeature': '确认删除该标注？',
        'project.confirm.deleteLayer': '确认删除图层？',
        'project.confirm.deleteAll': '确定要删除所有项目及其关联的所有图层、要素吗？此操作不可撤销！',
        'project.alert.deleteFailed': '删除失败，请检查网络或控制台',
        'project.alert.allCleared': '所有矢量项目已清空',
        'raster.confirm.delete': '确定从工作站移除此影像？该操作不可恢复。',
        'raster.confirm.clearDatabase': '注意：这将清空所有存储的遥感数据，确定吗？',
        'raster.prompt.mergeName': '请输入合成影像名称',
        'raster.prompt.extractName': '请输入提取影像名称',
        'raster.alert.mergeFailed': '合成失败，请检查波段兼容性',
        'raster.alert.extractFailed': '提取失败，请检查波段索引是否合法',
        'upload.alert.missingFiles': '缺少必要文件：{files}',
        'upload.alert.selectProjectFirst': '请先选择目标项目',
        'upload.alert.importSuccess': '导入成功：{imported} 个要素，{fields} 个字段',
        'upload.summary.partial': '上传完成\n成功 {success} 个\n失败 {failed} 个\n{details}',
        'ai.error.missingTargetPrompt': '请选择目标数据并输入指令',
        'ai.success.created': '已新建数据，ID: {id}',
        'ai.success.overwritten': '已成功覆盖原始数据',
        'ai.confirm.overwrite': '确认覆盖原始数据？此操作不可撤销。',
        'modal.selectRasterFirst': '请先上传影像',
        'modal.bandSuffix': '{count} 波段',
        'script.validation.running': '正在执行算法...',
        'script.validation.empty': '请输入脚本',
        'script.validation.ok': '✓ 语法检查通过',
        'script.history.empty': '暂无历史记录',
        'script.execute.idle': '执行脚本',
        'script.execute.running': '执行中...',
        'script.alert.selectRaster': '请选择至少一个输入影像',
        'script.toast.success': '脚本执行成功',
        'script.toast.failed': '执行失败: {message}',
    },
    en: {
        'page.title': 'Agent RSMarking | Intelligent Remote Sensing System Pro',
        'nav.layerCounter': 'Loaded Layers: {count}',
        'ui.loading.default': 'Processing...',
        'ui.loading.serverHint': 'Please wait while the server processes the data',
        'clip.currentRaster': 'Current raster:',
        'clip.noActiveRaster': 'No raster image is currently loaded',
        'clip.useActiveLayer': '-- Use current active layer --',
        'clip.selectKnifeLayer': '-- Select clip knife layer --',
        'clip.selectKnifeWarning': 'Please select a clip knife layer',
        'draw.none': 'No Tool Selected',
        'draw.active': 'Drawing: {tool}',
        'draw.tool.polygon': 'Polygon',
        'draw.tool.rectangle': 'Rectangle',
        'draw.tool.circle': 'Circle',
        'draw.tool.polyline': 'Line',
        'draw.tool.marker': 'Marker',
        'draw.tool.circlemarker': 'Sample Point',
        'sidebar.raster.waiting': 'Waiting for data to load...',
        'sidebar.raster.title': 'Raster Resources',
        'sidebar.raster.import': '+ Import',
        'sidebar.raster.bundle': 'Bundle: {id}',
        'sidebar.raster.members': '{count} items',
        'sidebar.raster.onMap': 'ON MAP',
        'sidebar.raster.spectrumTitle': 'Spectral query: click the map to sample a pixel',
        'sidebar.raster.attrTitle': 'Open attribute table',
        'sidebar.raster.removeTitle': 'Remove from workspace',
        'sidebar.vector.emptyProjects': 'No annotation projects yet',
        'sidebar.vector.title': 'Annotation Projects',
        'sidebar.vector.newProject': '+ New Project',
        'sidebar.vector.selectProject': '-- Select annotation project --',
        'sidebar.vector.projectTag': 'Project: {name}',
        'sidebar.vector.importTitle': 'Import Shapefile (auto-create layer)',
        'sidebar.vector.newLayerTitle': 'Create empty layer',
        'sidebar.vector.emptyLayers': 'No annotation layers created yet',
        'sidebar.vector.selectHint': 'Select a project from the dropdown first',
        'sidebar.vector.currentEditing': '● Currently editing',
        'sidebar.vector.clickToActivate': 'Click to activate editing',
        'sidebar.vector.attrTitle': 'Open attribute table',
        'sidebar.vector.deleteTitle': 'Delete layer',
        'project.prompt.projectName': 'Enter a new vector project name:',
        'project.prompt.projectDefault': 'Default Annotation Project',
        'project.prompt.layerName': 'Enter a new annotation layer name:',
        'project.prompt.layerDefault': 'Building Annotation',
        'project.alert.selectProjectFirst': 'Please select or create a vector project first.',
        'project.alert.selectLayerFirst': 'Please select or create a target annotation layer on the left first.',
        'project.confirm.deleteFeature': 'Delete this annotation?',
        'project.confirm.deleteLayer': 'Delete this layer?',
        'project.confirm.deleteAll': 'Delete all projects and all related layers and features? This cannot be undone.',
        'project.alert.deleteFailed': 'Delete failed. Please check the network or console.',
        'project.alert.allCleared': 'All vector projects have been cleared',
        'raster.confirm.delete': 'Remove this image from the workspace? This action cannot be undone.',
        'raster.confirm.clearDatabase': 'This will clear all stored remote sensing data. Continue?',
        'raster.prompt.mergeName': 'Enter a name for the merged image',
        'raster.prompt.extractName': 'Enter a name for the extracted image',
        'raster.alert.mergeFailed': 'Merge failed. Please check band compatibility.',
        'raster.alert.extractFailed': 'Extraction failed. Please check whether the band index is valid.',
        'upload.alert.missingFiles': 'Missing required files: {files}',
        'upload.alert.selectProjectFirst': 'Please select a target project first',
        'upload.alert.importSuccess': 'Import succeeded: {imported} features, {fields} fields',
        'upload.summary.partial': 'Upload finished\nSucceeded: {success}\nFailed: {failed}\n{details}',
        'ai.error.missingTargetPrompt': 'Please select a target dataset and enter a prompt',
        'ai.success.created': 'Created a new dataset. ID: {id}',
        'ai.success.overwritten': 'The original dataset has been overwritten successfully',
        'ai.confirm.overwrite': 'Overwrite the original dataset? This action cannot be undone.',
        'modal.selectRasterFirst': 'Please upload imagery first',
        'modal.bandSuffix': '{count} bands',
        'script.validation.running': 'Running algorithm...',
        'script.validation.empty': 'Please enter a script',
        'script.validation.ok': '✓ Syntax check passed',
        'script.history.empty': 'No history yet',
        'script.execute.idle': 'Run Script',
        'script.execute.running': 'Running...',
        'script.alert.selectRaster': 'Please select at least one input raster',
        'script.toast.success': 'Script executed successfully',
        'script.toast.failed': 'Execution failed: {message}',
    },
};

const literalCatalog = {
    en: {
        'AI 助手': 'AI Assistant',
        '空间裁剪': 'Spatial Clip',
        '导出视图': 'Export View',
        '清空数据': 'Clear Data',
        '界面语言': 'Language',
        '已载入图层: 0': 'Loaded Layers: 0',
        '矢量标注中心': 'Vector Annotation Center',
        '标注项目': 'Annotation Project',
        '+ 新建项目': '+ New Project',
        '-- 请选择或创建项目 --': '-- Select or create a project --',
        '标注图层': 'Annotation Layers',
        '添加图层': 'Add Layer',
        '绘图工具箱': 'Drawing Toolbox',
        '撤销': 'Delete Feature',
        '取消': 'Cancel',
        '退出': 'Exit',
        '未选择工具': 'No Tool Selected',
        '工具': 'Tools',
        '选择绘制工具': 'Choose a Drawing Tool',
        '面': 'Area',
        '多边形': 'Polygon',
        '矩形': 'Rectangle',
        '圆形': 'Circle',
        '线': 'Line',
        '线段': 'Line',
        '点': 'Point',
        '标记点': 'Marker',
        '采样点': 'Sample Point',
        '影像处理中心': 'Imagery Processing Center',
        '光谱处理': 'Spectral Processing',
        '多波段合成': 'Band Stacking',
        '波段提取': 'Band Extraction',
        '指数计算': 'Index Calculation',
        '植被差异指数 (NDVI)': 'Vegetation Difference Index (NDVI)',
        '分析地表植被覆盖度': 'Analyze surface vegetation coverage',
        '水体差异指数 (NDWI)': 'Water Difference Index (NDWI)',
        '增强水体特征显示': 'Enhance water feature visibility',
        '建筑差异指数 (NDBI)': 'Built-up Difference Index (NDBI)',
        '提取城镇建成区范围': 'Extract urban built-up areas',
        '改进型水体指数 (MNDWI)': 'Modified Water Index (MNDWI)',
        '更精准的城镇水体识别': 'More precise urban water detection',
        '要素提取': 'Feature Extraction',
        '植被自动提取': 'Auto Extract Vegetation',
        '水体自动提取': 'Auto Extract Water',
        '建筑形态提取': 'Building Form Extraction',
        '云部自动提取': 'Auto Extract Clouds',
        '自定义运算': 'Custom Operations',
        '通用栅格计算器': 'General Raster Calculator',
        '支持基于AST数学表达式运算': 'Supports AST-based math expressions',
        '脚本编程': 'Script Programming',
        'Python 脚本编辑器': 'Python Script Editor',
        '自定义遥感算法处理': 'Custom remote sensing algorithm processing',
        '变化检测': 'Change Detection',
        '多期影像变化检测': 'Multi-temporal Change Detection',
        '差值 / 比值 / 指数差值分析': 'Difference / Ratio / Index-difference analysis',
        '格式转换': 'Format Conversion',
        '矢量转栅格': 'Vector to Raster',
        '像素级对齐': 'Pixel-aligned output',
        '影像目录': 'Imagery Catalog',
        '暂无影像数据': 'No imagery data available',
        'Spatial Clip': 'Spatial Clip',
        '裁剪类型': 'Clip Type',
        '裁剪栅格': 'Clip Raster',
        '手绘裁剪影像': 'Draw a clipping area on the image',
        '裁剪矢量': 'Clip Vector',
        '范围过滤要素': 'Filter features by extent',
        '图层互裁': 'Layer-on-layer Clip',
        '图层裁剪图层': 'Use one layer to clip another',
        '当前激活影像': 'Current Active Raster',
        '裁剪范围来源': 'Clip Source',
        '影像范围': 'Image Extent',
        '用栅格 bounds': 'Use raster bounds',
        '手动绘制': 'Draw Manually',
        '在地图上绘制': 'Draw on the map',
        '目标矢量图层（被裁剪）': 'Target Vector Layer (to be clipped)',
        '裁剪刀图层（提供范围）': 'Clip Knife Layer (provides extent)',
        '裁剪刀图层与目标图层不能相同': 'The clip knife layer cannot be the same as the target layer',
        '开始裁剪': 'Start Clipping',
        'AI 空间智能助手': 'AI Spatial Assistant',
        '分析数据 · 智能修改元数据': 'Analyze data · Intelligently edit metadata',
        '目标数据': 'Target Data',
        '数据类型': 'Data Type',
        '栅格影像': 'Raster Imagery',
        '矢量图层': 'Vector Layer',
        '任务模式': 'Task Mode',
        '使用说明 / Instructions': 'Usage / Instructions',
        '分析模式': 'Analysis Mode',
        '修改模式': 'Modify Mode',
        '输出语言': 'Output Language',
        '中文': 'Chinese',
        '指令': 'Prompt',
        'AI 输出': 'AI Output',
        '下载分析报告': 'Download Analysis Report',
        '新建副本': 'Create Copy',
        '覆盖原始': 'Overwrite Original',
        '执行 AI 任务': 'Run AI Task',
        '返回工作站': 'Back to Workspace',
        '执行脚本': 'Run Script',
        '执行中...': 'Running...',
        '请输入脚本': 'Please enter a script',
        '暂无历史记录': 'No history yet',
    },
};

const attributeCatalog = {
    en: {
        title: {
            '上传 TIFF 影像': 'Upload TIFF imagery',
            '导入 Shapefile（需先选中图层）': 'Import Shapefile (select a layer first)',
            '刷新列表': 'Refresh list',
            '切换 2D / 3D 球形视图': 'Switch between 2D and 3D globe view',
        },
    },
};

let currentLanguage = DEFAULT_LANGUAGE;
let mutationObserver = null;
const subscribers = new Set();

function interpolate(template, params = {}) {
    return String(template).replace(/\{(\w+)\}/g, (_, key) => params[key] ?? '');
}

function normalizeLanguage(language) {
    if (!language) return DEFAULT_LANGUAGE;
    const normalized = String(language).toLowerCase();
    if (normalized.startsWith('en')) return 'en';
    return 'zh';
}

function translateLiteral(value) {
    if (!value) return value;
    return literalCatalog[currentLanguage]?.[value] ?? value;
}

function translateAttribute(attr, value) {
    if (!value) return value;
    return attributeCatalog[currentLanguage]?.[attr]?.[value] ?? value;
}

function translateTextNode(node) {
    const original = node.__rsOriginalText ?? node.nodeValue;
    node.__rsOriginalText = original;

    const trimmed = original.trim();
    if (!trimmed) return;

    const translated = translateLiteral(trimmed);
    if (translated === trimmed) {
        node.nodeValue = original;
        return;
    }

    const leading = original.match(/^\s*/)?.[0] ?? '';
    const trailing = original.match(/\s*$/)?.[0] ?? '';
    node.nodeValue = `${leading}${translated}${trailing}`;
}

function translateElementAttribute(element, attr) {
    const originalKey = `rsOriginal${attr.charAt(0).toUpperCase()}${attr.slice(1)}`;
    const original = element.dataset[originalKey] ?? element.getAttribute(attr);
    if (!original) return;

    element.dataset[originalKey] = original;
    element.setAttribute(attr, translateAttribute(attr, original));
}

export function getLanguage() {
    return currentLanguage;
}

export function getDateLocale() {
    return currentLanguage === 'en' ? 'en-US' : 'zh-CN';
}

export function t(key, params = {}) {
    const dictionary = messageCatalog[currentLanguage] ?? messageCatalog[DEFAULT_LANGUAGE];
    const fallback = messageCatalog[DEFAULT_LANGUAGE];
    const template = dictionary?.[key] ?? fallback?.[key] ?? key;
    return interpolate(template, params);
}

export function applyTranslations(root = document) {
    if (typeof document === 'undefined' || !root) return;

    document.documentElement.lang = currentLanguage === 'en' ? 'en' : 'zh-CN';
    document.title = t('page.title');

    const treeWalker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT,
        {
            acceptNode(node) {
                if (!node.nodeValue?.trim()) return NodeFilter.FILTER_REJECT;
                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                if (['SCRIPT', 'STYLE', 'TEXTAREA', 'OPTION'].includes(parent.tagName)) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        }
    );

    const textNodes = [];
    while (treeWalker.nextNode()) {
        textNodes.push(treeWalker.currentNode);
    }
    textNodes.forEach(translateTextNode);

    const scope = root.querySelectorAll ? root : document;
    scope.querySelectorAll('option').forEach((option) => {
        const original = option.dataset.rsOriginalText ?? option.textContent;
        option.dataset.rsOriginalText = original;
        option.textContent = translateLiteral(original);
    });
    scope.querySelectorAll('[title]').forEach((element) => translateElementAttribute(element, 'title'));
    scope.querySelectorAll('[placeholder]').forEach((element) => translateElementAttribute(element, 'placeholder'));

    const selector = document.getElementById('app-language-select');
    if (selector) selector.value = currentLanguage;
}

function notifySubscribers() {
    subscribers.forEach((callback) => {
        try {
            callback(currentLanguage);
        } catch (error) {
            console.error('[i18n] language subscriber failed:', error);
        }
    });
}

export function setLanguage(language) {
    const nextLanguage = normalizeLanguage(language);
    if (!SUPPORTED_LANGUAGES.has(nextLanguage) || nextLanguage === currentLanguage) {
        applyTranslations(document);
        return;
    }

    currentLanguage = nextLanguage;
    localStorage.setItem(STORAGE_KEY, currentLanguage);
    applyTranslations(document);
    notifySubscribers();
}

function bindLanguageSelector() {
    const selector = document.getElementById('app-language-select');
    if (!selector || selector.dataset.bound === 'true') return;

    selector.dataset.bound = 'true';
    selector.value = currentLanguage;
    selector.addEventListener('change', (event) => {
        setLanguage(event.target.value);
    });
}

function ensureObserver() {
    if (mutationObserver || typeof MutationObserver === 'undefined') return;

    mutationObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.TEXT_NODE) {
                    translateTextNode(node);
                } else if (node.nodeType === Node.ELEMENT_NODE) {
                    applyTranslations(node);
                }
            });
        });
    });

    mutationObserver.observe(document.body, {
        childList: true,
        subtree: true,
    });
}

export function initializeI18n() {
    currentLanguage = normalizeLanguage(localStorage.getItem(STORAGE_KEY) || DEFAULT_LANGUAGE);
    bindLanguageSelector();
    applyTranslations(document);
    ensureObserver();
}

export function onLanguageChange(callback) {
    subscribers.add(callback);
    return () => subscribers.delete(callback);
}
