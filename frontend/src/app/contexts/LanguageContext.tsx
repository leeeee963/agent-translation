import { createContext, useContext, useState, type ReactNode } from 'react';

type AppLanguage = 'en' | 'zh';

interface LanguageContextType {
  language: AppLanguage;
  setLanguage: (lang: AppLanguage) => void;
  t: (key: string) => string;
}

const translations: Record<string, Record<AppLanguage, string>> = {
  // Navigation
  'nav.tasks': { en: 'Translation Platform', zh: '多语言翻译平台' },
  'nav.newTask': { en: 'New Translation', zh: '新建翻译' },
  'nav.translation': { en: 'Translation', zh: '翻译' },
  'nav.create': { en: 'New Translation', zh: '新建翻译' },
  'nav.taskList': { en: 'Translations', zh: '翻译查看' },
  'nav.library': { en: 'Terminology', zh: '术语库' },
  'nav.settings': { en: 'Settings', zh: '设置' },

  // Common
  'common.cancel': { en: 'Cancel', zh: '取消' },
  'common.confirm': { en: 'Confirm', zh: '确认' },
  'common.delete': { en: 'Delete', zh: '删除' },
  'common.download': { en: 'Download', zh: '下载' },
  'common.edit': { en: 'Edit', zh: '编辑' },
  'common.save': { en: 'Save', zh: '保存' },
  'common.back': { en: 'Back', zh: '返回' },
  'common.next': { en: 'Next', zh: '下一步' },
  'common.start': { en: 'Start Translation', zh: '开始翻译' },
  'common.close': { en: 'Close', zh: '关闭' },
  'common.translating': { en: 'Translating...', zh: '翻译进行中...' },
  'common.search': { en: 'Search', zh: '搜索' },
  'common.menu': { en: 'Menu', zh: '菜单' },
  'common.collapseSidebar': { en: 'Collapse sidebar', zh: '收起侧栏' },
  'common.expandSidebar': { en: 'Expand sidebar', zh: '展开侧栏' },

  // File Upload
  'upload.title': { en: 'Upload Files', zh: '上传文件' },
  'upload.dragDrop': { en: 'Click or drag files here', zh: '点击上传或拖拽文件' },
  'upload.supportedFormats': { en: 'Supported formats', zh: '支持的格式' },
  'upload.selectedFiles': { en: 'Selected Files', zh: '已选文件' },
  'upload.addMore': { en: 'Add more files', zh: '继续上传' },
  'upload.unsupported': { en: 'Unsupported file format', zh: '不支持的文件格式' },

  // Language Selection
  'lang.title': { en: 'Target Languages', zh: '选择目标语言' },
  'lang.selectLanguages': { en: 'Search', zh: '搜索' },
  'lang.selected': { en: 'Selected', zh: '已选择' },
  'lang.noSelection': { en: 'No languages selected', zh: '未选择语言' },

  // Translation Mode
  'mode.title': { en: 'Pro', zh: 'Pro' },
  'mode.direct': { en: 'Direct Translation', zh: '直接翻译' },
  'mode.directDesc': { en: 'Translate immediately', zh: '立即翻译，无需翻译前审核' },
  'mode.glossary': { en: 'Glossary Mode', zh: '术语表模式' },
  'mode.glossaryDesc': { en: 'Higher quality · Review terms before starting', zh: '更高翻译质量 · 确认术语后开始翻译' },
  'mode.glossaryToggle': { en: 'Glossary', zh: '术语' },
  'mode.proInfoDesc': { en: 'Confirm terms first, then translate.', zh: '先确认术语，再开始翻译。' },
  'mode.libraryInfoTitle': { en: 'Terminology Library', zh: '术语库' },
  'mode.libraryInfoDesc': { en: 'Terms saved for good — smarter every time.', zh: '术语永久入库，越用越好用。' },

  // Domain
  'domain.title': { en: 'Terminology Library', zh: '术语库' },
  'domain.toggle': { en: 'Domain', zh: 'Domain' },
  'domain.select': { en: 'Select domains', zh: '选择术语域' },
  'domain.hint': { en: 'All domains (optional)', zh: '全部术语域（可选）' },
  'domain.infoTitle': { en: 'What is Domain matching?', zh: '什么是术语域匹配？' },
  'domain.infoDesc': { en: 'When Domain is ON, the AI looks up matching terms from your Terminology Library before translating — ensuring consistent use of your approved vocabulary.', zh: '开启 Domain 后，AI 在翻译前会从术语库中匹配已有术语，确保全文使用你审核过的标准译法。' },
  'domain.infoAvailable': { en: 'Domains in your library:', zh: '当前术语库中的域：' },
  'domain.noDomains': { en: 'No domains yet — add them in the Terminology Library.', zh: '暂无术语域，请前往术语库添加。' },
  'domain.selectedHint': { en: 'Terms from selected domains will be matched before translating to ensure consistency.', zh: '翻译前会从所选术语域中匹配术语，确保用词一致。' },
  'domain.unselectedHint': { en: 'Optional — select domains to enable terminology matching for higher quality.', zh: '可选 — 选择术语域后将启用术语匹配，提升翻译质量。' },
  'domain.disabledHint': { en: 'Enable Pro first', zh: '请先开启 Pro' },

  // Task List
  'tasks.title': { en: 'Translation Tasks', zh: '翻译任务' },
  'tasks.empty': { en: 'No tasks yet', zh: '暂无任务' },
  'tasks.emptyHint': { en: 'Upload files and select languages to start translating', zh: '上传文件并选择目标语言，即可开始翻译' },
  'tasks.active': { en: 'Active Tasks', zh: '进行中的任务' },
  'tasks.completed': { en: 'Completed Tasks', zh: '已完成' },
  'tasks.expandAll': { en: 'Expand All', zh: '展开全部' },
  'tasks.collapseAll': { en: 'Collapse All', zh: '收起全部' },

  // Task Toolbar
  'tasks.toolbar.search': { en: 'Search by filename...', zh: '搜索文件名...' },
  'tasks.toolbar.groupBy': { en: 'Group', zh: '分组' },
  'tasks.toolbar.thenBy': { en: 'Then', zh: '再按' },
  'tasks.toolbar.filterStatus': { en: 'Status', zh: '状态' },
  'tasks.toolbar.filterType': { en: 'File Type', zh: '文件类型' },
  'tasks.toolbar.saveView': { en: 'Save View', zh: '保存视图' },
  'tasks.toolbar.savedViews': { en: 'Views', zh: '视图' },
  'tasks.toolbar.custom': { en: 'Custom', zh: '自定义' },
  'tasks.toolbar.deleteView': { en: 'Delete', zh: '删除' },
  'tasks.toolbar.viewName': { en: 'View name', zh: '视图名称' },
  'tasks.toolbar.filter': { en: 'Filter', zh: '筛选' },
  'tasks.toolbar.grouping': { en: 'Group', zh: '分组' },
  'tasks.toolbar.addGroup': { en: 'Add group', zh: '添加分组' },
  'tasks.toolbar.groupCondition': { en: 'Set grouping', zh: '设置分组条件' },
  'tasks.toolbar.removeGroup': { en: 'Remove', zh: '移除' },

  // Group-by options
  'tasks.group.none': { en: 'No Grouping', zh: '不分组' },
  'tasks.group.status': { en: 'Status', zh: '状态' },
  'tasks.group.time': { en: 'Time', zh: '时间' },
  'tasks.group.fileType': { en: 'File Type', zh: '文件类型' },

  // Status group labels
  'tasks.groupStatus.active': { en: 'In Progress', zh: '进行中' },
  'tasks.groupStatus.error': { en: 'Failed', zh: '失败' },
  'tasks.groupStatus.completed': { en: 'Completed', zh: '已完成' },

  // Time bucket labels
  'tasks.groupTime.today': { en: 'Today', zh: '今天' },
  'tasks.groupTime.yesterday': { en: 'Yesterday', zh: '昨天' },
  'tasks.groupTime.last7Days': { en: 'Last 7 Days', zh: '过去7天' },
  'tasks.groupTime.last30Days': { en: 'Last 30 Days', zh: '过去30天' },
  'tasks.groupTime.older': { en: 'Older', zh: '更早' },

  // File type group
  'tasks.groupFileType.unknown': { en: 'Other', zh: '其他' },

  // Filter
  'tasks.filter.all': { en: 'All', zh: '全部' },
  'tasks.noResults': { en: 'No matching tasks', zh: '无匹配任务' },

  // Task Status
  'status.queued': { en: 'Queued', zh: '排队中' },
  'status.pending': { en: 'Pending', zh: '等待中' },
  'status.parsing': { en: 'Parsing', zh: '解析文件' },
  'status.terminology': { en: 'Extracting Glossary', zh: '提取术语表' },
  'status.awaiting_glossary_review': { en: 'Review', zh: '等待审核' },
  'status.translating': { en: 'Translating', zh: '翻译中' },
  'status.reviewing': { en: 'Reviewing', zh: '审校中' },
  'status.rebuilding': { en: 'Rebuilding', zh: '重建文件' },
  'status.done': { en: 'Completed', zh: '已完成' },
  'status.error': { en: 'Error', zh: '出错' },
  'status.cancelled': { en: 'Cancelled', zh: '已取消' },

  // Progress
  'progress.overall': { en: 'Overall', zh: '整体进度' },
  'progress.languages': { en: 'Languages', zh: '各语言进度' },
  'progress.downloadReady': { en: 'Ready', zh: '可下载' },
  'progress.downloadAll': { en: 'Download All', zh: '全部下载' },

  // Glossary
  'glossary.title': { en: 'Review Glossary', zh: '审核术语表' },
  'glossary.source': { en: 'Source', zh: '原文' },
  'glossary.translation': { en: 'Translation', zh: '译文' },
  'glossary.frequency': { en: 'Freq', zh: '频次' },
  'glossary.action': { en: 'Action', zh: '处理方式' },
  'glossary.category': { en: 'Category', zh: '类别' },
  'glossary.uncertain': { en: 'Uncertain', zh: '不确定' },
  'glossary.export': { en: 'Export', zh: '导出' },
  'glossary.confirmAndStart': { en: 'Confirm & Start Translation', zh: '确认术语表并开始翻译' },
  'glossary.copy': { en: 'Copy', zh: '复制' },
  'glossary.filterAll': { en: 'All', zh: '全部' },
  'glossary.filterUncertain': { en: 'Uncertain', zh: '不确定' },
  'glossary.terms': { en: 'terms', zh: '个术语' },
  'glossary.needReview': { en: 'Need Review', zh: '待审核' },
  'glossary.translationStrategy': { en: 'Translation Strategy', zh: '翻译策略' },
  'glossary.aiCategory': { en: 'AI Category', zh: 'AI分类' },
  'glossary.context': { en: 'Context', zh: '领域含义' },
  'glossary.contextPlaceholder': { en: 'Add context...', zh: '添加上下文说明...' },
  'glossary.copied': { en: 'Copied to clipboard', zh: '已复制到剪贴板' },
  'glossary.exported': { en: 'Exported successfully', zh: '导出成功' },
  'glossary.noTerms': { en: 'No terms to display', zh: '无术语可显示' },
  'glossary.reextract': { en: 'Re-extract', zh: '重新提取' },
  'glossary.saveToLibrary': { en: 'Save to Library', zh: '保存到术语库' },
  'glossary.review': { en: 'Review', zh: '审核' },
  'glossary.inline': { en: 'Glossary', zh: '术语表' },
  'glossary.reviewTitle': { en: 'Glossary Review', zh: '术语表审核' },
  'glossary.candidates': { en: 'candidates', zh: '个候选' },
  'glossary.reviewDesc': { en: 'AI has extracted term candidates. Review the strategy and translations for each term, then click "Start Translation".', zh: 'AI 已提取以下术语候选。请审核每个术语的策略和译文，然后点击「开始翻译」。' },
  'glossary.sourceFile': { en: 'Source file: ', zh: '来源文件：' },
  'glossary.filter': { en: 'Filter:', zh: '筛选：' },
  'glossary.libraryMatch': { en: 'In Library', zh: '库中已有' },
  'glossary.newlyExtracted': { en: 'New', zh: '新提取' },
  'glossary.onlyUncertain': { en: 'Uncertain only', zh: '仅不确定' },
  'glossary.reextracting': { en: 'Re-extracting...', zh: '重新提取中...' },
  'glossary.acceptAll': { en: 'Accept All (Default)', zh: '全部接受（默认策略）' },
  'glossary.startTranslation': { en: 'Start Translation', zh: '开始翻译' },
  'glossary.processing': { en: 'Processing...', zh: '处理中...' },
  'glossary.unsaveFromLibrary': { en: 'Cancel save to library', zh: '取消保存到术语库' },
  'glossary.inLibrary': { en: 'In Library', zh: '已在库中' },
  'glossary.colSource': { en: 'Source', zh: '原文' },
  'glossary.colSaveToLibrary': { en: 'Save to Library', zh: '存入术语库' },
  'glossary.colLibraryHint': { en: 'Library terms show icon; check to save new terms', zh: '库中术语显示图标，勾选可将新术语存入术语库' },
  'glossary.colStrategy': { en: 'Strategy', zh: '策略' },
  'glossary.colAiCategory': { en: 'AI Category', zh: 'AI分类' },
  'glossary.colFrequency': { en: 'Frequency', zh: '频次' },
  'glossary.colContext': { en: 'Context', zh: '领域含义' },
  'glossary.catProperNoun': { en: 'Proper Noun', zh: '专有名词' },
  'glossary.catPerson': { en: 'Person', zh: '人名' },
  'glossary.catPlace': { en: 'Place', zh: '地名' },
  'glossary.catBrand': { en: 'Brand', zh: '品牌' },
  'glossary.catDomainTerm': { en: 'Domain Term', zh: '领域词' },
  'glossary.catAmbiguous': { en: 'Ambiguous', zh: '多义词' },
  'glossary.strategyEnforce': { en: 'Enforce', zh: '约束' },
  'glossary.strategyPreserve': { en: 'Keep', zh: '保留' },
  'glossary.strategySkip': { en: 'Free', zh: '自由' },
  'glossary.strategyEnforceHint': { en: 'Lock translation, strictly followed', zh: '锁定译文，严格遵守' },
  'glossary.strategyPreserveHint': { en: 'Leave original, skip translation', zh: '保持原文，跳过翻译' },
  'glossary.strategySkipHint': { en: 'No constraint, translate as needed', zh: '放开限制，自行翻译' },
  'glossary.reextractTooltip': { en: 'Discard current results and re-extract terms', zh: '丢弃当前结果，重新让AI提取术语' },
  'glossary.fromLibrary': { en: 'Lib', zh: '库' },
  'glossary.helpTitle': { en: 'Glossary Review Guide', zh: '术语表审核说明' },
  'glossary.helpStrategyTitle': { en: 'Translation Strategies', zh: '翻译策略' },
  'glossary.helpEnforce': { en: 'Enforce — Lock translation, strictly followed.', zh: '约束 — 锁定译文，严格遵守。' },
  'glossary.helpPreserve': { en: 'Keep — Leave original, skip translation.', zh: '保留 — 保持原文，跳过翻译。' },
  'glossary.helpSkip': { en: 'Free — No constraint, translate as needed.', zh: '自由 — 放开限制，自行翻译。' },
  'glossary.helpLibTitle': { en: 'Icon Guide', zh: '图标说明' },
  'glossary.helpLibInLibrary': { en: 'In library — auto-matched for reuse.', zh: '已入库术语，自动匹配复用。' },
  'glossary.helpLibNew': { en: 'New term — check to save to library.', zh: '新提取术语，勾选可存入术语库。' },
  'glossary.fromLibraryTitle': { en: 'From terminology library', zh: '来自术语库' },
  'glossary.clickToEdit': { en: 'Click to edit', zh: '点击编辑' },
  'glossary.aiUncertain': { en: 'AI uncertain', zh: 'AI不确定' },
  'glossary.noteTranslationDiffers': { en: 'AI suggests a different translation than the library — please verify', zh: 'AI建议的译法与术语库不同，请确认' },
  'glossary.noteMissingTranslations': { en: 'Library is missing translations for: {langs} — please add', zh: '术语库缺少目标语言翻译：{langs}，请补充' },
  'glossary.noFilterResults': { en: 'No terms match the current filter', zh: '没有符合筛选条件的术语' },
  'glossary.bottomSummary': { en: '{total} term candidates', zh: '共 {total} 个术语候选' },
  'glossary.bottomLibrary': { en: ', {lib} from library, {new} newly extracted', zh: '，其中 {lib} 个来自术语库，{new} 个为新提取' },
  'glossary.bottomConstraint': { en: ', {count} will be used as translation constraints', zh: '，{count} 个将纳入翻译约束' },
  'glossary.startTranslationArrow': { en: 'Start Translation →', zh: '开始翻译 →' },
  'glossary.libSyncTitle': { en: 'Update terminology library?', zh: '是否同步更新术语库？' },
  'glossary.libSyncDesc': { en: 'You have modified translations for the following library terms:', zh: '检测到您修改了以下术语库中术语的译文：' },
  'glossary.libSyncExplain': { en: 'Choose "Update Library" to sync changes back. Future translations will use the new terms.', zh: '选择「更新术语库」将把修改同步回术语库，未来翻译会使用新译法。' },
  'glossary.libSyncThisTime': { en: 'This time only', zh: '仅本次使用' },
  'glossary.libSyncUpdate': { en: 'Update Library', zh: '更新术语库' },

  // Glossary Actions
  'action.enforce': { en: 'Enforce', zh: '强制使用' },
  'action.preserve': { en: 'Preserve', zh: '保留原文' },
  'action.skip': { en: 'Skip', zh: '跳过' },
  'action.hard': { en: 'Enforce', zh: '强制使用' },
  'action.keep_original': { en: 'Preserve', zh: '保留原文' },

  // Glossary Categories
  'category.person': { en: 'Person Name', zh: '人名' },
  'category.place': { en: 'Place Name', zh: '地名' },
  'category.brand': { en: 'Brand', zh: '品牌' },
  'category.technical': { en: 'Technical Term', zh: '专业术语' },
  'category.general': { en: 'General', zh: '通用' },
  'category.unknown': { en: 'Unclassified', zh: '未分类' },

  // Settings
  'settings.title': { en: 'Settings', zh: '系统配置' },
  'settings.api': { en: 'API Configuration', zh: 'API 配置' },
  'settings.apiKey': { en: 'API Key', zh: 'API 密钥' },
  'settings.apiEndpoint': { en: 'API Endpoint', zh: '接口地址' },
  'settings.modelName': { en: 'Model Name', zh: '模型名称' },
  'settings.prompt': { en: 'Prompt Template', zh: '提示词模板' },
  'settings.promptDesc': { en: 'Customize the translation prompt', zh: '自定义翻译提示词' },
  'settings.saved': { en: 'Settings saved successfully', zh: '设置已保存' },
  'settings.tabApi': { en: 'API', zh: 'API' },
  'settings.tabPrompt': { en: 'Prompt', zh: '提示词' },
  'settings.promptVariables': { en: 'Variables', zh: '可用变量' },

  // Banner
  'banner.uploadFirst': { en: 'Please upload files first', zh: '请先上传文件' },
  'banner.selectLang': { en: 'Please select at least one target language', zh: '请至少选择一种目标语言' },
  'banner.submitted': { en: 'translation tasks submitted', zh: '个翻译任务已提交' },
  'banner.glossaryConfirmed': { en: 'Glossary confirmed, translation started.', zh: '术语已确认，翻译任务已启动。' },

  // Errors
  'error.submitFailed': { en: 'Failed to submit translation tasks', zh: '提交翻译任务失败' },
  'error.cancelFailed': { en: 'Failed to cancel task', zh: '取消任务失败' },
  'error.deleteFailed': { en: 'Failed to delete task', zh: '删除任务失败' },

  // Selection
  'tasks.selected': { en: '{count} selected', zh: '已选 {count} 项' },
  'tasks.selectHint': { en: 'Select tasks to delete', zh: '选择要删除的任务' },

  // Theme
  'theme.light': { en: 'Light', zh: '浅色' },
  'theme.dark': { en: 'Dark', zh: '深色' },

  // Library page
  'library.title': { en: 'Terminology Library', zh: '术语库管理' },
  'library.back': { en: 'Back to Translation', zh: '返回翻译' },
  'library.domains': { en: 'Domains', zh: '术语域' },
  'library.addDomain': { en: 'Add Domain', zh: '新建域' },
  'library.addTerm': { en: 'Add Term', zh: '添加术语' },
  'library.import': { en: 'Import', zh: '导入' },
  'library.export': { en: 'Export', zh: '导出' },
  'library.batchDelete': { en: 'Batch Delete', zh: '批量删除' },
  'library.noTerms': { en: 'No terms in this domain', zh: '该域暂无术语' },
  'library.selectDomain': { en: 'Select a domain', zh: '请选择一个术语域' },
  'library.termSource': { en: 'Source Term', zh: '原文术语' },
  'library.termStrategy': { en: 'Strategy', zh: '策略' },
  'library.termContext': { en: 'Context', zh: '上下文' },
  'library.confirmDelete': { en: 'Confirm delete?', zh: '确认删除？' },
  'library.domainName': { en: 'Domain Name', zh: '域名称' },
  'library.domainDesc': { en: 'Description', zh: '描述' },

  // Languages
  'languages.en': { en: 'English', zh: '英语' },
  'languages.zh': { en: 'Chinese', zh: '中文' },
  'languages.es': { en: 'Spanish', zh: '西班牙语' },
  'languages.fr': { en: 'French', zh: '法语' },
  'languages.de': { en: 'German', zh: '德语' },
  'languages.ja': { en: 'Japanese', zh: '日语' },
  'languages.ko': { en: 'Korean', zh: '韩语' },
  'languages.pt': { en: 'Portuguese', zh: '葡萄牙语' },
  'languages.ru': { en: 'Russian', zh: '俄语' },
  'languages.ar': { en: 'Arabic', zh: '阿拉伯语' },
  'languages.it': { en: 'Italian', zh: '意大利语' },
  'languages.nl': { en: 'Dutch', zh: '荷兰语' },
  'languages.pl': { en: 'Polish', zh: '波兰语' },
  'languages.tr': { en: 'Turkish', zh: '土耳其语' },
  'languages.vi': { en: 'Vietnamese', zh: '越南语' },
  'languages.th': { en: 'Thai', zh: '泰语' },

  // Review changes
  'review.title': { en: 'Review Changes', zh: '审阅修改' },
  'review.export': { en: 'Export', zh: '导出' },
  'review.original': { en: 'Original', zh: '原文' },
  'review.translated': { en: 'Translated', zh: '翻译稿' },
  'review.reviewed': { en: 'Reviewed', zh: '审校稿' },

  // Phase cards
  'phase.glossary.title': { en: 'Glossary Review', zh: '术语表审核' },
  'phase.glossary.descActive': { en: 'candidates to review', zh: '个候选术语待确认' },
  'phase.glossary.descDone': { en: 'terms confirmed', zh: '个术语已确认' },
  'phase.translation.title': { en: 'Translation & Review', zh: '翻译 & 审校进度' },
  'phase.translation.descPending': { en: 'Starts after glossary review', zh: '术语审核完成后开始翻译' },
  'phase.translation.descActive': { en: 'target languages', zh: '个目标语言' },
  'phase.translation.descDone': { en: 'languages translated', zh: '个语言翻译完成' },
  'phase.review.title': { en: 'Naturalness Review', zh: '自然度审校' },
  'phase.review.descActive': { en: 'Optimizing fluency', zh: '优化译文流畅度和表达' },
  'phase.review.descDone': { en: 'Review complete', zh: '审校完成' },
  'phase.status.active': { en: 'In Progress', zh: '进行中' },

  // Step indicator
  'step.extractTerms': { en: 'Extract', zh: '提取' },
  'step.confirmTerms': { en: 'Confirm', zh: '确认' },
  'step.translate': { en: 'Translate', zh: '翻译' },
  'step.review': { en: 'Review', zh: '审校' },
  'step.complete': { en: 'Done', zh: '完成' },
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<AppLanguage>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('app_language') as AppLanguage;
      if (saved === 'en' || saved === 'zh') return saved;
    }
    return 'zh';
  });

  const handleSetLanguage = (lang: AppLanguage) => {
    setLanguage(lang);
    localStorage.setItem('app_language', lang);
  };

  const t = (key: string): string => {
    return translations[key]?.[language] || key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage: handleSetLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
