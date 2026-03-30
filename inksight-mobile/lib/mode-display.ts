/**
 * 内置模式展示名/简介，与 backend/core/mode_catalog.py 的 BUILTIN_CATALOG 对齐。
 * 自定义/广场模式不在此表时回退到接口返回的 display_name / description。
 */
type CatalogRow = { zh: { name: string; tip: string }; en: { name: string; tip: string } };

const BUILTIN: Record<string, CatalogRow> = {
  DAILY: {
    zh: { name: '每日', tip: '语录、书籍推荐、冷知识的综合日报' },
    en: { name: 'Everyday', tip: 'A daily digest: quotes, book picks, and fun facts' },
  },
  WEATHER: {
    zh: { name: '天气', tip: '实时天气和未来趋势看板' },
    en: { name: 'Weather', tip: 'Current weather and forecast dashboard' },
  },
  ZEN: {
    zh: { name: '禅意', tip: '一个大字表达当下心境' },
    en: { name: 'Zen', tip: 'A single character to reflect your mood' },
  },
  BRIEFING: {
    zh: { name: '简报', tip: '科技热榜 + AI 洞察简报' },
    en: { name: 'Briefing', tip: 'Tech trends + AI insights briefing' },
  },
  STOIC: {
    zh: { name: '斯多葛', tip: '每日一句哲学箴言' },
    en: { name: 'Stoic', tip: 'A daily stoic quote' },
  },
  POETRY: {
    zh: { name: '诗词', tip: '古诗词与简短注解' },
    en: { name: 'Poetry', tip: 'Classical poetry with a short note' },
  },
  ARTWALL: {
    zh: { name: '画廊', tip: '根据时令生成黑白艺术画' },
    en: { name: 'Gallery', tip: 'Seasonal black & white generative art' },
  },
  ALMANAC: {
    zh: { name: '老黄历', tip: '农历、节气、宜忌信息' },
    en: { name: 'Almanac', tip: 'Lunar calendar, solar terms, and daily luck' },
  },
  RECIPE: {
    zh: { name: '食谱', tip: '按时段推荐三餐方案' },
    en: { name: 'Recipe', tip: 'Meal ideas based on time of day' },
  },
  COUNTDOWN: {
    zh: { name: '倒计时', tip: '重要日程倒计时/正计时' },
    en: { name: 'Countdown', tip: 'Countdown / count-up for important events' },
  },
  MEMO: {
    zh: { name: '便签', tip: '展示自定义便签文字' },
    en: { name: 'Memo', tip: 'Show your custom memo text' },
  },
  HABIT: {
    zh: { name: '打卡', tip: '每日习惯完成进度' },
    en: { name: 'Habits', tip: 'Daily habit progress' },
  },
  ROAST: {
    zh: { name: '毒舌', tip: '轻松幽默的吐槽风格内容' },
    en: { name: 'Roast', tip: 'Lighthearted, sarcastic daily roast' },
  },
  FITNESS: {
    zh: { name: '健身', tip: '居家健身动作与建议' },
    en: { name: 'Fitness', tip: 'At-home workout tips' },
  },
  LETTER: {
    zh: { name: '慢信', tip: '来自不同时空的一封慢信' },
    en: { name: 'Letter', tip: 'A slow letter from another time' },
  },
  THISDAY: {
    zh: { name: '今日历史', tip: '历史上的今天重大事件' },
    en: { name: 'On This Day', tip: 'Major events in history today' },
  },
  RIDDLE: {
    zh: { name: '猜谜', tip: '谜题与脑筋急转弯' },
    en: { name: 'Riddle', tip: 'Riddles and brain teasers' },
  },
  QUESTION: {
    zh: { name: '每日一问', tip: '值得思考的开放式问题' },
    en: { name: 'Daily Question', tip: 'A thought-provoking open question' },
  },
  BIAS: {
    zh: { name: '认知偏差', tip: '认知偏差与心理效应' },
    en: { name: 'Bias', tip: 'A cognitive bias or psychological effect' },
  },
  STORY: {
    zh: { name: '微故事', tip: '可在 30 秒内读完的微故事' },
    en: { name: 'Micro Story', tip: 'A complete micro fiction in three parts' },
  },
  LIFEBAR: {
    zh: { name: '进度条', tip: '年/月/周/人生进度条' },
    en: { name: 'Life Bar', tip: 'Progress bars for year / month / week / life' },
  },
  CHALLENGE: {
    zh: { name: '微挑战', tip: '每天一个 5 分钟微挑战' },
    en: { name: 'Challenge', tip: 'A 5-minute daily micro challenge' },
  },
  WORD_OF_THE_DAY: {
    zh: { name: '每日一词', tip: '每日精选一个英语单词，展示其拼写与释义' },
    en: { name: 'Word of the Day', tip: 'One English word with a short explanation' },
  },
  MY_QUOTE: {
    zh: { name: '自定义语录', tip: '可随机生成，或输入你自己的语录内容' },
    en: { name: 'Custom Quote', tip: 'Supports custom input or random generation' },
  },
  MY_ADAPTIVE: {
    zh: { name: '自适应照片', tip: '上传本地照片，自适应 4.2" 墨水屏显示' },
    en: { name: 'Adaptive Photo', tip: 'Upload a local photo and auto-fit it to the 4.2" e-ink screen' },
  },
  CALENDAR: {
    zh: { name: '日历', tip: '展示月历、日期与相关日程信息' },
    en: { name: 'Calendar', tip: 'Show calendar, date, and related schedule info' },
  },
  TIMETABLE: {
    zh: { name: '课程表', tip: '展示今日或本周课程安排' },
    en: { name: 'Timetable', tip: 'Show today or weekly class schedule' },
  },
};

export function modeDisplayName(modeId: string, locale: 'zh' | 'en', apiFallback: string) {
  const row = BUILTIN[modeId.toUpperCase()];
  if (!row) {
    return apiFallback;
  }
  return locale === 'en' ? row.en.name : row.zh.name;
}

export function localizeCatalogMode(
  mode: { mode_id: string; display_name: string; description: string },
  locale: 'zh' | 'en',
): { display_name: string; description: string } {
  const row = BUILTIN[mode.mode_id.toUpperCase()];
  if (!row) {
    return { display_name: mode.display_name, description: mode.description };
  }
  if (locale === 'en') {
    return {
      display_name: row.en.name,
      description: row.en.tip || mode.description,
    };
  }
  return {
    display_name: row.zh.name,
    description: mode.description || row.zh.tip,
  };
}
