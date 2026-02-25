/**
 * 临时回归验证脚本：http://127.0.0.1:18080/config 模式展示行为
 * 运行: npx playwright install chromium && node scripts/regression-config-verify.mjs
 */
import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:18080/config';
const results = [];

function log(step, pass, detail) {
  const status = pass ? 'PASS' : 'FAIL';
  results.push({ step, status, detail });
  console.log(`[${status}] ${step}: ${detail}`);
}

async function waitForPage(page, selector, maxWait = 10000) {
  const step = 2000;
  let elapsed = 0;
  while (elapsed < maxWait) {
    const el = await page.locator(selector).first();
    if (await el.count() > 0) {
      try {
        await el.waitFor({ state: 'visible', timeout: 3000 });
        return true;
      } catch (_) {}
    }
    await page.waitForTimeout(step);
    elapsed += step;
  }
  return false;
}

async function main() {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    page.setDefaultTimeout(15000);

    // 打开页面
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const hasModes = await page.locator('#modes').count() > 0;
    if (!hasModes) {
      log('0. 页面加载', false, '未在 DOM 中找到 #modes');
    } else {
      log('0. 页面加载', true, '页面可访问，DOM 含 #modes');
    }
    // 无 MAC 时 configForm 默认隐藏，为验证模式区域行为临时显示表单
    await page.evaluate(() => {
      const f = document.getElementById('configForm');
      if (f) f.style.display = 'block';
    });
    await page.waitForTimeout(300);

    // Step 1: 内容模式区域
    const hasLabel = await page.locator('label.lbl:has-text("内容模式（多选）")').count() > 0;
    const hasCore = await page.locator('text=推荐核心（10）').count() > 0;
    const hasTools = await page.locator('text=工具模式').count() > 0;
    const hasToggle = await page.locator('#modesMoreToggle:has-text("展开更多模式")').count() > 0;
    const moreWrap = await page.locator('#modesMoreWrap');
    const moreHidden = (await moreWrap.getAttribute('style') || '').includes('display:none') || (await moreWrap.evaluate(el => getComputedStyle(el).display === 'none'));
    log('1. 内容模式区域', hasLabel && hasCore && hasTools && hasToggle, 
      hasLabel && hasCore && hasTools && hasToggle 
        ? '包含推荐核心(10)、工具模式、展开更多模式按钮；更多模式默认未展开' 
        : `label=${hasLabel} 推荐核心=${hasCore} 工具模式=${hasTools} 按钮=${hasToggle} 更多隐藏=${moreHidden}`);

    // Step 2: 更多模式 展开/收起
    const btn = page.locator('#modesMoreToggle');
    await btn.click();
    await page.waitForTimeout(300);
    const expandedAfter = await page.locator('#modesMoreWrap').evaluate(el => getComputedStyle(el).display !== 'none');
    const hasMoreLabel = await page.locator('#modesMoreWrap .tcl:has-text("更多模式")').count() > 0;
    await btn.click();
    await page.waitForTimeout(300);
    const collapsedAfter = await page.locator('#modesMoreWrap').evaluate(el => getComputedStyle(el).display === 'none');
    log('2. 更多模式折叠', expandedAfter && hasMoreLabel && collapsedAfter, 
      expandedAfter && collapsedAfter ? '点击展开后出现更多模式，再次点击可收起' : `展开后可见=${expandedAfter} 收起后隐藏=${collapsedAfter}`);

    // 再展开以便后续点击 RIDDLE
    await btn.click();
    await page.waitForTimeout(200);

    // Step 3: 核心区点击 DAILY，缩略图更新
    const configFormVisible = await page.locator('#configForm').evaluate(el => getComputedStyle(el).display !== 'none');
    if (configFormVisible) {
      const dailyChip = page.locator('#modesCore .ch[data-m="DAILY"]').first();
      await dailyChip.click();
      await page.waitForTimeout(300);
      const title = await page.locator('#modeThumbTitle').textContent();
      const desc = await page.locator('#modeThumbDesc').textContent();
      const thumbOk = (title || '').includes('DAILY') && (desc || '').length > 0;
      log('3. 核心区点击 DAILY 缩略图', thumbOk, thumbOk ? `标题/描述已更新: ${(title||'').slice(0,30)}...` : `title=${title} desc=${(desc||'').slice(0,50)}`);
    } else {
      log('3. 核心区点击 DAILY 缩略图', false, '配置表单未显示(可能仅显示 wizard)');
    }

    // Step 4: 更多模式里点击 RIDDLE，可选中且展开保持
    const riddleChip = page.locator('#modesMore .ch[data-m="RIDDLE"]').first();
    await riddleChip.click();
    await page.waitForTimeout(300);
    const riddleSelected = await riddleChip.evaluate(el => el.classList.contains('sel'));
    const moreStillVisible = await page.locator('#modesMoreWrap').evaluate(el => getComputedStyle(el).display !== 'none');
    log('4. 更多模式 RIDDLE', riddleSelected && moreStillVisible, 
      riddleSelected && moreStillVisible ? 'RIDDLE 已选中且更多模式区域保持展开' : `选中=${riddleSelected} 展开保持=${moreStillVisible}`);

    // Step 5: hover tooltip（chip 有 data-tip 且为描述文案，CSS :hover::after 会显示）
    const chipWithTip = page.locator('#modes .ch[data-m="DAILY"]').first();
    await chipWithTip.hover();
    await page.waitForTimeout(400);
    const dataTip = await chipWithTip.getAttribute('data-tip');
    const tipOk = !!(dataTip && dataTip.includes('日报'));
    log('5. hover tooltip', tipOk, tipOk ? 'chip 具 data-tip 描述文案（hover 时 CSS 显示 tooltip）' : `data-tip=${(dataTip||'').slice(0,40)}`);

    // Step 6 & 7: Setup Wizard 第2步预设（需无配置 mac 触发）
    await page.goto(`${BASE}?mac=AA:BB:CC:DD:EE:FF`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);
    const wizardVisible = await page.locator('#setupWizard').evaluate(el => getComputedStyle(el).display !== 'none' && el.style.display !== 'none');
    if (wizardVisible) {
      // 进入第2步（当前是 step1，点一次“下一步”到 step2）
      await page.locator('button:has-text("下一步")').first().click();
      await page.waitForTimeout(800);
      const step2Visible = await page.locator('#wizStep2').evaluate(el => getComputedStyle(el).display !== 'none');
      const presetCount = await page.locator('.wiz-preset').count();
      const recommendedSelected = await page.locator('.wiz-preset.selected[data-preset="recommended"]').count() > 0;
      const recommendedText = await page.locator('.wiz-preset[data-preset="recommended"]').textContent();
      const literaryText = await page.locator('.wiz-preset[data-preset="literary"]').textContent();
      const efficiencyText = await page.locator('.wiz-preset[data-preset="efficiency"]').textContent();
      const minimalText = await page.locator('.wiz-preset[data-preset="minimal"]').textContent();
      const hasRec = (recommendedText || '').includes('DAILY') && (recommendedText || '').includes('WEATHER') && (recommendedText || '').includes('ZEN') && (recommendedText || '').includes('STOIC') && (recommendedText || '').includes('BRIEFING');
      const hasLit = (literaryText || '').includes('ZEN') && (literaryText || '').includes('POETRY') && (literaryText || '').includes('ARTWALL') && (literaryText || '').includes('ALMANAC');
      const hasEff = (efficiencyText || '').includes('BRIEFING') && (efficiencyText || '').includes('WEATHER') && (efficiencyText || '').includes('COUNTDOWN') && (efficiencyText || '').includes('DAILY');
      const hasMin = (minimalText || '').includes('STOIC') && (minimalText || '').includes('ZEN');
      log('6. Wizard 第2步预设', step2Visible && presetCount === 4 && recommendedSelected, 
        step2Visible && presetCount === 4 ? `4 套预设，默认选中推荐` : `step2可见=${step2Visible} 预设数=${presetCount} 默认推荐=${recommendedSelected}`);
      log('7. 预设文案', hasRec && hasLit && hasEff && hasMin, 
        hasRec && hasLit && hasEff && hasMin ? '推荐/文艺/效率/极简文案符合' : `推荐=${hasRec} 文艺=${hasLit} 效率=${hasEff} 极简=${hasMin}`);
    } else {
      log('6. Wizard 第2步预设', false, '未触发 Wizard（该 mac 可能已有配置）');
      log('7. 预设文案', false, '依赖 Step6 先通过');
    }

  } catch (e) {
    console.error(e);
    log('运行异常', false, e.message || String(e));
  } finally {
    if (browser) await browser.close();
  }

  // 汇总
  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL').length;
  console.log('\n--- 汇总 ---');
  console.log(`PASS: ${passed}, FAIL: ${failed}`);
  process.exit(failed > 0 ? 1 : 0);
}

main();
