// NOTE: 此组件已废弃，设备级 AI 配置已从 UI 中移除。
// 为兼容旧引用，保留一个空的占位导出；新代码不应再使用该组件。
"use client";

// 空组件占位：旧代码如果仍引入 LlmProviderConfig，不会导致编译失败；新代码不应再使用。
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function LlmProviderConfig() {
  return null;
}
