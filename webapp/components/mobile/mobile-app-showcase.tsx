"use client";

import Link from "next/link";
import { useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Bell,
  BookOpen,
  Compass,
  Cpu,
  Feather,
  Heart,
  House,
  Languages,
  Palette,
  PenTool,
  Plus,
  RefreshCcw,
  Send,
  Settings2,
  Share2,
  ShieldCheck,
  Sparkles,
  SunMedium,
  UserRound,
  Wifi,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type Locale, withLocalePath } from "@/lib/i18n";

type TabId = "today" | "browse" | "create" | "device" | "me";
type BrowseSegmentId = "history" | "favorites" | "modes";

type CopyText = {
  zh: string;
  en: string;
};

type ApiItem = {
  method: string;
  path: string;
  note: CopyText;
  isNew?: boolean;
};

type ScreenItem = {
  name: string;
  detail: CopyText;
  api: string[];
};

type MetricItem = {
  label: CopyText;
  value: string;
};

type TabDefinition = {
  id: TabId;
  label: CopyText;
  title: CopyText;
  eyebrow: CopyText;
  summary: CopyText;
  accent: string;
  icon: LucideIcon;
  metrics: MetricItem[];
  screens: ScreenItem[];
  interactions: CopyText[];
  apis: ApiItem[];
};

type PageGroup = {
  group: CopyText;
  description: CopyText;
  screens: string[];
};

type Phase = {
  name: string;
  duration: CopyText;
  focus: CopyText;
  tasks: CopyText[];
};

type BackendExtension = {
  method: string;
  path: string;
  title: CopyText;
  detail: CopyText;
};

const tr = (locale: Locale, text: CopyText) => (locale === "en" ? text.en : text.zh);

const appTabs: TabDefinition[] = [
  {
    id: "today",
    label: { zh: "首页", en: "Today" },
    title: { zh: "Today 首页", en: "Today Feed" },
    eyebrow: { zh: "沉浸式慢信息阅读", en: "Immersive slow-content reading" },
    summary: {
      zh: "全屏卡片流承载每日慢信息，支持左右切换模式、下拉“墨韵”刷新、双击收藏和推送到设备。",
      en: "A calm full-screen card feed for daily slow content, with mode swiping, ink refresh, favorite gestures, and device push.",
    },
    accent: "#1A1A1A",
    icon: House,
    metrics: [
      { label: { zh: "首屏模式", en: "Modes up front" }, value: "5+" },
      { label: { zh: "刷新节奏", en: "Refresh cadence" }, value: "2s" },
      { label: { zh: "核心交互", en: "Core gestures" }, value: "4" },
    ],
    screens: [
      { name: "TodayScreen", detail: { zh: "全屏内容卡片流，支持模式切换与即时预览。", en: "A full-screen card stream with mode switching and instant preview." }, api: ["GET /preview?persona={mode}", "GET /content/today"] },
      { name: "ContentDetailSheet", detail: { zh: "底部详情面板呈现结构化文字、来源和分享动作。", en: "A bottom sheet for structured details, source text, and share actions." }, api: ["local cache"] },
      { name: "PushToDeviceSheet", detail: { zh: "从当前内容快速选择设备并推送。", en: "A quick target picker to send content to a device." }, api: ["POST /device/{mac}/apply-preview"] },
    ],
    interactions: [
      { zh: "左右滑动切换模式，强调慢节奏和专注感。", en: "Swipe horizontally to move between modes with a deliberate pace." },
      { zh: "下拉触发 2 秒“墨韵”刷新动画，替代快节奏 spinner。", en: "Pull to refresh with a 2-second ink ripple instead of a busy spinner." },
      { zh: "双击收藏，长按弹出 iOS Context Menu。", en: "Double tap to favorite, long-press for an iOS-style context menu." },
    ],
    apis: [
      { method: "GET", path: "/preview?persona={mode}", note: { zh: "复用现有渲染 PNG 预览。", en: "Reuse the existing PNG preview renderer." } },
      { method: "GET", path: "/content/today", note: { zh: "返回结构化内容供卡片与通知复用。", en: "Structured content payload for cards and notifications." }, isNew: true },
      { method: "POST", path: "/device/{mac}/apply-preview", note: { zh: "把当前内容推送到指定设备。", en: "Send the current card to a selected device." } },
    ],
  },
  {
    id: "browse",
    label: { zh: "发现", en: "Browse" },
    title: { zh: "Browse 发现", en: "Browse Hub" },
    eyebrow: { zh: "历史、收藏、模式目录", en: "History, favorites, and mode catalog" },
    summary: {
      zh: "通过三段式切换查看历史内容、收藏库与 22+ 模式目录，兼顾回看与探索。",
      en: "A segmented browse surface for history, favorites, and a 22+ mode catalog.",
    },
    accent: "#8E8E93",
    icon: Compass,
    metrics: [
      { label: { zh: "目录密度", en: "Catalog density" }, value: "3-col" },
      { label: { zh: "缓存时长", en: "Cache window" }, value: "5m" },
      { label: { zh: "内容回看", en: "Lookback" }, value: "50" },
    ],
    screens: [
      { name: "BrowseScreen", detail: { zh: "历史、收藏、模式三段切换的总入口。", en: "Segmented control entry point for history, favorites, and modes." }, api: ["GET /device/{mac}/history", "GET /device/{mac}/favorites"] },
      { name: "ModeCatalogScreen", detail: { zh: "按 3 列网格展示模式，支持启用与预览。", en: "A three-column mode grid with enable and preview actions." }, api: ["GET /modes"] },
      { name: "ContentDetailScreen", detail: { zh: "全屏详情承接长文、来源和复制。", en: "Full-screen detail view for long-form reading, source notes, and copy." }, api: ["local cache"] },
    ],
    interactions: [
      { zh: "按日期分组回看历史内容，收藏与历史共享卡片组件。", en: "Review content by day groupings, with shared history and favorite cards." },
      { zh: "模式目录使用语义化 Lucide 图标，统一去掉 emoji。", en: "Use semantic Lucide icons throughout the mode catalog with no emoji." },
      { zh: "点击条目进入全屏详情，再决定分享、复制或推送。", en: "Open any entry into a full-screen detail page before sharing or sending." },
    ],
    apis: [
      { method: "GET", path: "/device/{mac}/history", note: { zh: "读取设备历史内容。", en: "Read device-side content history." } },
      { method: "GET", path: "/device/{mac}/favorites", note: { zh: "读取已收藏内容。", en: "Load favorited content." } },
      { method: "GET", path: "/modes", note: { zh: "获取模式目录与启用状态。", en: "Fetch the mode catalog and enabled state." } },
    ],
  },
  {
    id: "create",
    label: { zh: "创作", en: "Create" },
    title: { zh: "Create 创作中心", en: "Create Studio" },
    eyebrow: { zh: "中心按钮强化 UGC", en: "Center action for UGC creation" },
    summary: {
      zh: "中间突出按钮承接 AI 生成、模板创建与空白编辑三条路径，实时联动预览图。",
      en: "A raised center button anchors AI generation, templates, and blank editing with live preview feedback.",
    },
    accent: "#2D2D2D",
    icon: Plus,
    metrics: [
      { label: { zh: "创建路径", en: "Creation paths" }, value: "3" },
      { label: { zh: "实时预览", en: "Live preview" }, value: "Yes" },
      { label: { zh: "表单深度", en: "Editor depth" }, value: "Form" },
    ],
    screens: [
      { name: "CreateScreen", detail: { zh: "AI 生成、模板、空白三种入口。", en: "Three entry paths: AI, template, and blank mode." }, api: ["—"] },
      { name: "ModeEditorScreen", detail: { zh: "表单式编辑器，联动渲染预览。", en: "A structured editor with linked preview rendering." }, api: ["POST /modes/custom/preview", "POST /modes/custom"] },
      { name: "AIGenerateScreen", detail: { zh: "通过自然语言描述生成新模式。", en: "Generate a mode from a natural-language prompt." }, api: ["POST /modes/generate"] },
    ],
    interactions: [
      { zh: "中心按钮略高于 Tab Bar，使用墨色圆形背景和白色加号。", en: "The center tab rises above the bar with an ink-dark circle and a white plus sign." },
      { zh: "模板卡片和 AI 生成共享同一套字段模型，便于后续落到 Expo。", en: "Templates and AI generation share a common field model for later Expo implementation." },
      { zh: "实时预览复用现有 webapp 的渲染心智模型。", en: "Live preview follows the same rendering model already used in the web app." },
    ],
    apis: [
      { method: "POST", path: "/modes/custom/preview", note: { zh: "提交临时表单并返回预览。", en: "Submit draft form data and return a preview." } },
      { method: "POST", path: "/modes/custom", note: { zh: "保存自定义模式。", en: "Persist a custom mode." } },
      { method: "POST", path: "/modes/generate", note: { zh: "基于 prompt 自动生成模式配置。", en: "Generate a new mode config from a prompt." } },
    ],
  },
  {
    id: "device",
    label: { zh: "设备", en: "Device" },
    title: { zh: "Device 设备管理", en: "Device Console" },
    eyebrow: { zh: "多设备状态与配网", en: "Multi-device status and provisioning" },
    summary: {
      zh: "覆盖设备列表、详情、配置、固件升级与 BLE 配网，是硬件用户的主工作台。",
      en: "The command center for device owners, spanning status, configuration, firmware, and BLE provisioning.",
    },
    accent: "#007AFF",
    icon: Cpu,
    metrics: [
      { label: { zh: "状态轮询", en: "Status polling" }, value: "10s" },
      { label: { zh: "BLE 向导", en: "BLE flow" }, value: "4-step" },
      { label: { zh: "共享成员", en: "Member views" }, value: "2+" },
    ],
    screens: [
      { name: "DeviceListScreen", detail: { zh: "多设备列表与在线状态。", en: "A list of devices with online status." }, api: ["GET /user/devices", "GET /device/{mac}/state"] },
      { name: "DeviceDetailScreen", detail: { zh: "仪表盘聚合电量、模式和内容预览。", en: "A dashboard with battery, mode, and current content preview." }, api: ["GET /device/{mac}/state", "GET /config/{mac}"] },
      { name: "ProvisioningScreen", detail: { zh: "蓝牙 4 步向导完成认领与 Wi-Fi 配置。", en: "A four-step BLE wizard for claiming and Wi-Fi setup." }, api: ["POST /device/{mac}/claim-token"] },
    ],
    interactions: [
      { zh: "状态卡片优先显示电池、在线、当前模式，降低认知切换。", en: "Status cards foreground battery, connectivity, and active mode for quick scanning." },
      { zh: "BLE 配网提供 QR 降级路径，避免固件尚未支持时卡死。", en: "BLE provisioning includes a QR fallback path for firmware gaps." },
      { zh: "固件和成员管理保持列表式信息架构，贴近 iOS 设置层级。", en: "Firmware and member management keep a settings-style list hierarchy." },
    ],
    apis: [
      { method: "GET", path: "/user/devices", note: { zh: "读取当前用户全部设备。", en: "Load all devices for the current user." }, isNew: true },
      { method: "GET", path: "/device/{mac}/state", note: { zh: "设备状态、电池与模式概览。", en: "Device state with battery and mode metadata." } },
      { method: "GET", path: "/firmware/releases/latest", note: { zh: "查询最新固件版本。", en: "Fetch the latest firmware release." } },
    ],
  },
  {
    id: "me",
    label: { zh: "我的", en: "Me" },
    title: { zh: "Me 我的", en: "Profile & Settings" },
    eyebrow: { zh: "账号、偏好、语言", en: "Account, preferences, and locale" },
    summary: {
      zh: "承接个人资料、通知、语言、缓存和关于信息，同时也是首次使用引导与登录入口。",
      en: "Profile, notifications, language, cache, and onboarding all live in a calm personal center.",
    },
    accent: "#34C759",
    icon: UserRound,
    metrics: [
      { label: { zh: "偏好项", en: "Preference groups" }, value: "5" },
      { label: { zh: "通知策略", en: "Notification modes" }, value: "Daily" },
      { label: { zh: "安全存储", en: "Secure storage" }, value: "JWT" },
    ],
    screens: [
      { name: "ProfileScreen", detail: { zh: "账号信息与个人摘要。", en: "Profile summary with account details." }, api: ["GET /auth/me"] },
      { name: "SettingsScreen", detail: { zh: "语言、通知、缓存与关于。", en: "Language, notifications, cache, and about settings." }, api: ["GET /user/preferences", "PUT /user/preferences"] },
      { name: "OnboardingScreen", detail: { zh: "首次使用引导内容与设备分流。", en: "An onboarding flow that splits hardware and content-only users." }, api: ["—"] },
    ],
    interactions: [
      { zh: "语言和通知偏好直接映射后端 `user_preferences`。", en: "Language and notification preferences map directly to `user_preferences`." },
      { zh: "登录、注册、引导保持无 Tab 结构，避免主导航噪音。", en: "Login, registration, and onboarding sit outside the main tab shell." },
      { zh: "设置页遵循 iOS 列表感，弱化强操作按钮。", en: "Settings favor a native iOS list feel over button-heavy layouts." },
    ],
    apis: [
      { method: "GET", path: "/auth/me", note: { zh: "读取当前登录用户资料。", en: "Read the current signed-in user." } },
      { method: "GET", path: "/user/preferences", note: { zh: "加载 App 偏好设置。", en: "Load app preference settings." }, isNew: true },
      { method: "PUT", path: "/user/preferences", note: { zh: "更新语言、推送与 widget 偏好。", en: "Update language, push, and widget preferences." }, isNew: true },
    ],
  },
];

const pageGroups: PageGroup[] = [
  {
    group: { zh: "首页 Today", en: "Today" },
    description: { zh: "首页卡片流与详情层。", en: "Feed and detail surfaces." },
    screens: ["TodayScreen", "ContentDetailSheet", "PushToDeviceSheet"],
  },
  {
    group: { zh: "发现 Browse", en: "Browse" },
    description: { zh: "历史、收藏、模式与内容详情。", en: "History, favorites, modes, and detail screens." },
    screens: ["BrowseScreen", "ModeCatalogScreen", "ContentDetailScreen", "FavoriteCollectionScreen"],
  },
  {
    group: { zh: "创作 Create", en: "Create" },
    description: { zh: "创建入口、模板选择与模式编辑。", en: "Entry, templates, and editing." },
    screens: ["CreateScreen", "ModeEditorScreen", "AIGenerateScreen", "TemplatePickerScreen"],
  },
  {
    group: { zh: "设备 Device", en: "Device" },
    description: { zh: "列表、详情、配置、成员、固件与配网。", en: "List, detail, config, members, firmware, and provisioning." },
    screens: ["DeviceListScreen", "DeviceDetailScreen", "DeviceConfigScreen", "ProvisioningScreen", "MembersScreen", "FirmwareScreen", "ShareSheetScreen"],
  },
  {
    group: { zh: "我的 Me", en: "Me" },
    description: { zh: "账号、设置、引导与通知偏好。", en: "Profile, settings, onboarding, and notification preferences." },
    screens: ["ProfileScreen", "SettingsScreen", "LoginScreen", "RegisterScreen", "OnboardingScreen", "NotificationScheduleScreen"],
  },
];

const colorTokens = [
  { name: "Paper", hex: "#FAFAF8" },
  { name: "Surface", hex: "#F5F5F0" },
  { name: "Ink", hex: "#1A1A1A" },
  { name: "Secondary", hex: "#8E8E93" },
  { name: "Tertiary", hex: "#C7C7CC" },
  { name: "Accent", hex: "#007AFF" },
  { name: "Success", hex: "#34C759" },
  { name: "Danger", hex: "#FF3B30" },
];

const backendExtensions: BackendExtension[] = [
  { method: "POST", path: "/push/register", title: { zh: "注册推送设备", en: "Register push device" }, detail: { zh: "记录 Expo Push Token、平台与时区。", en: "Store Expo Push token, platform, and timezone." } },
  { method: "DELETE", path: "/push/unregister", title: { zh: "取消推送注册", en: "Remove push registration" }, detail: { zh: "停用指定终端的推送能力。", en: "Disable push delivery for a specific device." } },
  { method: "GET", path: "/user/preferences", title: { zh: "读取用户偏好", en: "Read preferences" }, detail: { zh: "为语言、通知和 widget 提供统一配置。", en: "Power language, notification, and widget settings." } },
  { method: "PUT", path: "/user/preferences", title: { zh: "更新用户偏好", en: "Update preferences" }, detail: { zh: "同步本地偏好与后端存储。", en: "Sync local app preferences back to the backend." } },
  { method: "GET", path: "/content/today", title: { zh: "结构化今日内容", en: "Structured daily content" }, detail: { zh: "支持卡片、通知、widget 复用。", en: "Shared by cards, notifications, and widgets." } },
  { method: "GET", path: "/widget/{mac}/data", title: { zh: "Widget JSON 数据", en: "Widget JSON data" }, detail: { zh: "让原生小组件直接渲染内容。", en: "Allow native widgets to render without PNG screenshots." } },
];

const roadmap: Phase[] = [
  {
    name: "Phase 1",
    duration: { zh: "3-4 周", en: "3-4 weeks" },
    focus: { zh: "MVP：脚手架、认证、首页/发现/设备/我的", en: "MVP: scaffold, auth, Today/Browse/Device/Me" },
    tasks: [
      { zh: "Expo Router + Zustand + React Query 基础设施", en: "Expo Router + Zustand + React Query foundation" },
      { zh: "登录注册、JWT 安全存储、基础缓存", en: "Auth flow, JWT secure storage, and base caching" },
      { zh: "Today / Browse / Device / Me 四大主路径", en: "The four core product surfaces" },
    ],
  },
  {
    name: "Phase 2",
    duration: { zh: "2-3 周", en: "2-3 weeks" },
    focus: { zh: "设备管理强化", en: "Deepen device management" },
    tasks: [
      { zh: "设备详情、配置表单、共享成员", en: "Device detail, config forms, and shared members" },
      { zh: "模式切换、刷新控制、固件升级", en: "Mode switching, refresh control, and firmware update UI" },
    ],
  },
  {
    name: "Phase 3",
    duration: { zh: "3-4 周", en: "3-4 weeks" },
    focus: { zh: "移动独有能力", en: "Mobile-native capabilities" },
    tasks: [
      { zh: "BLE 配网、推送通知、桌面小组件", en: "BLE provisioning, push notifications, and widgets" },
      { zh: "分享图生成与触觉反馈调优", en: "Sharing flows and haptic tuning" },
    ],
  },
  {
    name: "Phase 4",
    duration: { zh: "2 周", en: "2 weeks" },
    focus: { zh: "打磨发布", en: "Polish and ship" },
    tasks: [
      { zh: "动画、离线模式、国际化完善", en: "Motion, offline resilience, and i18n hardening" },
      { zh: "提审素材、截图与构建发布", en: "Store assets, screenshots, and release builds" },
    ],
  },
];

const browseSegments = {
  history: {
    label: { zh: "历史", en: "History" },
    items: [
      { title: "诗词", body: "人间有味是清欢", time: "08:00" },
      { title: "每日推荐", body: "阻碍行动的障碍将成为行动本身", time: "09:15" },
      { title: "天气", body: "晴 18°C，适合散步", time: "10:20" },
    ],
  },
  favorites: {
    label: { zh: "收藏", en: "Favorites" },
    items: [
      { title: "慢信", body: "写给三个月后的自己", time: "Pinned" },
      { title: "禅意", body: "静", time: "Pinned" },
      { title: "微故事", body: "她把月光装进旧信封", time: "Pinned" },
    ],
  },
  modes: {
    label: { zh: "模式", en: "Modes" },
    items: [
      { title: "诗词", body: "已启用", time: "Active" },
      { title: "天气", body: "已启用", time: "Active" },
      { title: "画廊", body: "可预览", time: "Preview" },
      { title: "禅意", body: "已启用", time: "Active" },
      { title: "简报", body: "可预览", time: "Preview" },
      { title: "习惯", body: "已启用", time: "Active" },
    ],
  },
} satisfies Record<BrowseSegmentId, { label: CopyText; items: { title: string; body: string; time: string }[] }>;

const modeIcons: { name: string; icon: LucideIcon }[] = [
  { name: "诗词", icon: Feather },
  { name: "天气", icon: SunMedium },
  { name: "简报", icon: BookOpen },
  { name: "画廊", icon: Palette },
  { name: "习惯", icon: ShieldCheck },
  { name: "创作", icon: PenTool },
];

function PhoneShell({
  locale,
  activeTab,
  browseSegment,
  setBrowseSegment,
  setActiveTab,
}: {
  locale: Locale;
  activeTab: TabDefinition;
  browseSegment: BrowseSegmentId;
  setBrowseSegment: (segment: BrowseSegmentId) => void;
  setActiveTab: (tabId: TabId) => void;
}) {
  return (
    <div className="mx-auto w-full max-w-[380px] rounded-[44px] border border-[#d6d1c7] bg-[linear-gradient(180deg,#f9f7f1_0%,#ece8dd_100%)] p-3 shadow-[0_30px_90px_-40px_rgba(26,26,26,0.5)]">
      <div className="overflow-hidden rounded-[34px] border border-black/5 bg-[#FAFAF8]">
        <div className="flex items-center justify-between px-6 pb-3 pt-4 text-[12px] text-[#1A1A1A]">
          <span>9:41</span>
          <div className="flex items-center gap-1.5 text-[#8E8E93]">
            <Wifi size={12} strokeWidth={1.8} />
            <div className="h-2.5 w-6 rounded-full border border-current p-[1px]">
              <div className="h-full w-4 rounded-full bg-current" />
            </div>
          </div>
        </div>

        <div className="min-h-[680px] px-4 pb-5">
          {activeTab.id === "today" ? <TodayPhone locale={locale} /> : null}
          {activeTab.id === "browse" ? <BrowsePhone locale={locale} browseSegment={browseSegment} setBrowseSegment={setBrowseSegment} /> : null}
          {activeTab.id === "create" ? <CreatePhone locale={locale} /> : null}
          {activeTab.id === "device" ? <DevicePhone locale={locale} /> : null}
          {activeTab.id === "me" ? <MePhone locale={locale} /> : null}
        </div>

        <div className="border-t border-black/8 bg-[rgba(249,249,245,0.94)] px-3 pb-6 pt-3 backdrop-blur-md">
          <div className="flex items-end justify-between">
            {appTabs.map((tab) => {
              const Icon = tab.icon;
              const selected = tab.id === activeTab.id;
              const isCenter = tab.id === "create";
              if (isCenter) {
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className="flex min-w-[68px] flex-col items-center text-center"
                  >
                    <div className="mb-1 -mt-7 flex h-14 w-14 items-center justify-center rounded-full bg-[#2D2D2D] text-white shadow-[0_16px_30px_-18px_rgba(45,45,45,0.9)] transition-transform duration-300 hover:-translate-y-0.5">
                      <Icon size={24} strokeWidth={1.8} />
                    </div>
                    <span className={`font-serif text-[11px] ${selected ? "text-[#1A1A1A]" : "text-[#A0A0A0]"}`}>
                      {tr(locale, tab.label)}
                    </span>
                  </button>
                );
              }

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className="flex min-w-[62px] flex-col items-center gap-1 text-center"
                >
                  <Icon size={20} strokeWidth={1.8} color={selected ? "#2D2D2D" : "#A0A0A0"} />
                  <span className={`font-serif text-[11px] ${selected ? "text-[#2D2D2D]" : "text-[#A0A0A0]"}`}>
                    {tr(locale, tab.label)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function TodayPhone({ locale }: { locale: Locale }) {
  return (
    <div className="space-y-4">
      <div className="px-2 pt-1">
        <p className="font-serif text-[30px] text-[#1A1A1A]">{locale === "en" ? "March 15" : "三月十五"}</p>
        <p className="mt-1 text-sm text-[#8E8E93]">{locale === "en" ? "Saturday · Lunar Feb 16" : "乙巳年 · 二月十六 · 周六"}</p>
      </div>

      <div className="rounded-[24px] border border-black/5 bg-white px-5 py-5 shadow-[0_8px_30px_-24px_rgba(26,26,26,0.3)]">
        <div className="flex items-center justify-between text-xs uppercase tracking-[0.3em] text-[#8E8E93]">
          <span>{locale === "en" ? "Poetry" : "诗词"}</span>
          <Heart size={16} strokeWidth={1.8} />
        </div>
        <div className="px-2 py-7 text-center">
          <p className="font-serif text-[24px] leading-[2.1] tracking-[0.18em] text-[#1A1A1A]">人间有味是清欢</p>
          <div className="mx-auto my-4 h-px w-12 bg-[#E5E5EA]" />
          <p className="font-serif text-sm text-[#8E8E93]">{locale === "en" ? "Su Shi · Huan Xi Sha" : "苏轼 · 《浣溪沙》"}</p>
        </div>
        <div className="rounded-[16px] border border-[#E8E8E4] bg-[#F5F5F0] p-4">
          <p className="text-center text-[11px] text-[#A0A0A0]">{locale === "en" ? "E-ink preview" : "墨水屏预览效果"}</p>
          <div className="mt-3 rounded-[12px] border border-black/5 bg-white px-4 py-5 text-center font-serif text-[13px] leading-7 text-[#1A1A1A]">
            <p>三月十五 · 诗词</p>
            <p className="mt-3 text-[18px]">人间有味是清欢</p>
            <p className="mt-2 text-[#8E8E93]">- 苏轼 -</p>
          </div>
        </div>
        <div className="mt-5 flex items-center justify-around border-t border-[#F0F0F0] pt-4 text-xs text-[#8E8E93]">
          <span className="inline-flex items-center gap-1.5"><RefreshCcw size={14} strokeWidth={1.8} />{locale === "en" ? "Refresh" : "换一首"}</span>
          <span className="inline-flex items-center gap-1.5"><Share2 size={14} strokeWidth={1.8} />{locale === "en" ? "Share" : "分享"}</span>
          <span className="inline-flex items-center gap-1.5"><Send size={14} strokeWidth={1.8} />{locale === "en" ? "To device" : "推送到设备"}</span>
        </div>
      </div>

      <div className="flex justify-center gap-2">
        <div className="h-1.5 w-8 rounded-full bg-[#1A1A1A]" />
        <div className="h-1.5 w-2 rounded-full bg-[#D0D0D0]" />
        <div className="h-1.5 w-2 rounded-full bg-[#D0D0D0]" />
        <div className="h-1.5 w-2 rounded-full bg-[#D0D0D0]" />
      </div>

      <div className="flex items-center justify-between rounded-[18px] border border-black/5 bg-white px-4 py-3 shadow-[0_8px_20px_-24px_rgba(26,26,26,0.45)]">
        <div className="inline-flex items-center gap-2 text-sm text-[#1A1A1A]">
          <SunMedium size={16} strokeWidth={1.8} />
          <span>{locale === "en" ? "Sunny 18°C" : "晴 18°C"}</span>
        </div>
        <span className="text-xs text-[#8E8E93]">{locale === "en" ? "Good for a walk" : "适合出行"}</span>
      </div>
    </div>
  );
}

function BrowsePhone({
  locale,
  browseSegment,
  setBrowseSegment,
}: {
  locale: Locale;
  browseSegment: BrowseSegmentId;
  setBrowseSegment: (segment: BrowseSegmentId) => void;
}) {
  const current = browseSegments[browseSegment];

  return (
    <div className="space-y-4">
      <div className="px-2 pt-1">
        <p className="font-serif text-[30px] font-semibold text-[#1A1A1A]">{locale === "en" ? "Browse" : "发现"}</p>
        <p className="mt-1 text-sm text-[#8E8E93]">{locale === "en" ? "History, favorites, and modes" : "历史、收藏、模式目录"}</p>
      </div>

      <div className="flex rounded-[14px] bg-[#E5E5EA] p-1">
        {(Object.keys(browseSegments) as BrowseSegmentId[]).map((segment) => {
          const selected = segment === browseSegment;
          return (
            <button
              key={segment}
              type="button"
              onClick={() => setBrowseSegment(segment)}
              className={`flex-1 rounded-[11px] px-3 py-2 text-sm transition-all ${selected ? "bg-white text-[#1A1A1A] shadow-sm" : "text-[#8E8E93]"}`}
            >
              {tr(locale, browseSegments[segment].label)}
            </button>
          );
        })}
      </div>

      {browseSegment === "modes" ? (
        <div className="grid grid-cols-3 gap-3">
          {modeIcons.map(({ name, icon: Icon }, index) => (
            <div key={name} className="rounded-[18px] border border-black/5 bg-white px-2 py-4 text-center shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
              <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-[#F5F5F0] text-[#1A1A1A]">
                <Icon size={18} strokeWidth={1.8} />
              </div>
              <p className="mt-2 text-xs font-medium text-[#1A1A1A]">{name}</p>
              <p className={`mt-1 text-[10px] ${index % 2 === 0 ? "text-[#34C759]" : "text-[#8E8E93]"}`}>
                {index % 2 === 0 ? (locale === "en" ? "Enabled" : "已启用") : (locale === "en" ? "Preview" : "可预览")}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="px-1 text-xs font-medium text-[#8E8E93]">{locale === "en" ? "Today" : "今天"}</p>
          {current.items.map((item) => (
            <div key={`${browseSegment}-${item.title}`} className="flex gap-3 rounded-[18px] border border-black/5 bg-white p-3 shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[14px] border border-[#E8E8E4] bg-[#F5F5F0] text-[11px] text-[#8E8E93]">
                {locale === "en" ? "Preview" : "预览"}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-[#1A1A1A]">{item.title}</p>
                  <span className="text-[11px] text-[#C7C7CC]">{item.time}</span>
                </div>
                <p className="mt-1 text-sm leading-5 text-[#3C3C43]">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CreatePhone({ locale }: { locale: Locale }) {
  const createOptions = [
    { icon: Sparkles, title: locale === "en" ? "AI Generate" : "AI 生成", desc: locale === "en" ? "Describe a mood or ritual" : "一句描述生成新模式" },
    { icon: Palette, title: locale === "en" ? "Templates" : "模板套用", desc: locale === "en" ? "Start from a proven structure" : "基于成熟结构改写" },
    { icon: PenTool, title: locale === "en" ? "Blank Mode" : "空白模式", desc: locale === "en" ? "Craft from scratch" : "从零配置字段与渲染" },
  ];

  return (
    <div className="space-y-4">
      <div className="px-2 pt-1">
        <p className="font-serif text-[30px] font-semibold text-[#1A1A1A]">{locale === "en" ? "Create" : "创作"}</p>
        <p className="mt-1 text-sm text-[#8E8E93]">{locale === "en" ? "Templates, AI, and live preview" : "模板、AI 生成、实时预览"}</p>
      </div>

      <div className="space-y-3">
        {createOptions.map(({ icon: Icon, title, desc }) => (
          <div key={title} className="flex items-center gap-3 rounded-[18px] border border-black/5 bg-white p-4 shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#F5F5F0] text-[#1A1A1A]">
              <Icon size={18} strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-sm font-medium text-[#1A1A1A]">{title}</p>
              <p className="mt-1 text-xs text-[#8E8E93]">{desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-[22px] border border-black/5 bg-white p-4 shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#1A1A1A]">{locale === "en" ? "Mode editor" : "模式编辑器"}</p>
            <p className="mt-1 text-xs text-[#8E8E93]">{locale === "en" ? "Prompt + schedule + style" : "Prompt + 刷新策略 + 样式"}</p>
          </div>
          <span className="rounded-full bg-[#F5F5F0] px-3 py-1 text-[11px] text-[#1A1A1A]">{locale === "en" ? "Live" : "实时"}</span>
        </div>
        <div className="mt-4 grid gap-3">
          <div className="rounded-[14px] bg-[#F5F5F0] px-4 py-3 text-sm text-[#8E8E93]">
            {locale === "en" ? "Prompt: write a calm daily note for deep work." : "Prompt: 生成适合深度工作的平静日签。"}
          </div>
          <div className="rounded-[14px] bg-[#F5F5F0] px-4 py-3 text-sm text-[#8E8E93]">
            {locale === "en" ? "Refresh every 60 minutes, serif headline, compact footer." : "每 60 分钟刷新，衬线标题，紧凑页脚。"}
          </div>
          <div className="rounded-[16px] border border-[#E8E8E4] bg-[#FAFAF8] p-4">
            <p className="text-center text-[11px] text-[#A0A0A0]">{locale === "en" ? "Live preview" : "实时预览"}</p>
            <div className="mt-2 rounded-[12px] bg-white px-4 py-5 text-center font-serif text-[17px] leading-7 text-[#1A1A1A]">
              {locale === "en" ? "Stay with one thing." : "守住一件事。"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DevicePhone({ locale }: { locale: Locale }) {
  const rows = [
    { label: locale === "en" ? "Mode config" : "模式配置", value: locale === "en" ? "Poetry" : "诗词" },
    { label: locale === "en" ? "Refresh strategy" : "刷新策略", value: locale === "en" ? "Random · 60m" : "随机 · 60分钟" },
    { label: locale === "en" ? "LLM provider" : "LLM 提供商", value: "DeepSeek" },
    { label: locale === "en" ? "Members" : "共享成员", value: locale === "en" ? "2 users" : "2人" },
    { label: locale === "en" ? "Firmware" : "固件升级", value: "v2.1.0" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between px-2 pt-1">
        <div>
          <p className="font-serif text-[30px] font-semibold text-[#1A1A1A]">{locale === "en" ? "Study Ink" : "书房墨鱼"}</p>
          <p className="mt-1 text-sm text-[#8E8E93]">{locale === "en" ? "Device dashboard and BLE setup" : "设备仪表盘与 BLE 配网"}</p>
        </div>
        <span className="pt-2 text-sm text-[#007AFF]">{locale === "en" ? "Back" : "返回"}</span>
      </div>

      <div className="grid grid-cols-3 rounded-[22px] border border-black/5 bg-white px-4 py-5 text-center shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
        <div>
          <p className="text-2xl font-light text-[#1A1A1A]">85%</p>
          <p className="mt-1 text-[11px] text-[#8E8E93]">{locale === "en" ? "Battery" : "电池"}</p>
        </div>
        <div className="border-x border-[#E5E5EA]">
          <p className="text-2xl font-light text-[#34C759]">●</p>
          <p className="mt-1 text-[11px] text-[#8E8E93]">{locale === "en" ? "Online" : "在线"}</p>
        </div>
        <div>
          <p className="text-2xl font-light text-[#1A1A1A]">{locale === "en" ? "Poetry" : "诗词"}</p>
          <p className="mt-1 text-[11px] text-[#8E8E93]">{locale === "en" ? "Mode" : "当前模式"}</p>
        </div>
      </div>

      <div className="rounded-[22px] border border-black/5 bg-white p-4 shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
        <p className="text-sm font-medium text-[#1A1A1A]">{locale === "en" ? "Current display" : "当前显示内容"}</p>
        <div className="mt-3 rounded-[18px] border border-[#E8E8E4] bg-[#F5F5F0] p-5 text-center font-serif text-[17px] leading-8 text-[#1A1A1A]">
          人间有味是清欢
          <p className="text-xs text-[#8E8E93]">- 苏轼 -</p>
        </div>
        <button type="button" className="mt-4 w-full rounded-full bg-[#007AFF] px-4 py-2.5 text-sm font-medium text-white">
          {locale === "en" ? "Refresh now" : "立即刷新"}
        </button>
      </div>

      <div className="space-y-px overflow-hidden rounded-[20px] border border-black/5 bg-white shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between px-4 py-3.5">
            <span className="text-sm text-[#1A1A1A]">{row.label}</span>
            <span className={`text-sm ${row.label === (locale === "en" ? "Firmware" : "固件升级") ? "text-[#34C759]" : "text-[#8E8E93]"}`}>{row.value} &rsaquo;</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MePhone({ locale }: { locale: Locale }) {
  const settings = [
    { icon: Bell, title: locale === "en" ? "Notifications" : "通知", subtitle: locale === "en" ? "Daily at 8:00" : "每日 8:00 推送" },
    { icon: Languages, title: locale === "en" ? "Language" : "语言", subtitle: locale === "en" ? "Chinese / English" : "中文 / English" },
    { icon: Settings2, title: locale === "en" ? "Cache & privacy" : "缓存与隐私", subtitle: locale === "en" ? "1.0 MB local cache" : "本地缓存约 1.0 MB" },
    { icon: ShieldCheck, title: locale === "en" ? "About InkSight" : "关于 InkSight", subtitle: locale === "en" ? "Zen-like mobile companion" : "慢信息移动伴侣" },
  ];

  return (
    <div className="space-y-4">
      <div className="px-2 pt-1">
        <p className="font-serif text-[30px] font-semibold text-[#1A1A1A]">{locale === "en" ? "Me" : "我的"}</p>
        <p className="mt-1 text-sm text-[#8E8E93]">{locale === "en" ? "Account, preferences, and onboarding" : "账号、偏好与首次引导"}</p>
      </div>

      <div className="rounded-[24px] border border-black/5 bg-white p-5 shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#F5F5F0] text-[#1A1A1A]">
            <UserRound size={22} strokeWidth={1.8} />
          </div>
          <div>
            <p className="text-lg font-medium text-[#1A1A1A]">wangcong</p>
            <p className="mt-1 text-sm text-[#8E8E93]">{locale === "en" ? "Slow information collector" : "慢信息收藏者"}</p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {settings.map(({ icon: Icon, title, subtitle }) => (
          <div key={title} className="flex items-center gap-3 rounded-[18px] border border-black/5 bg-white p-4 shadow-[0_8px_18px_-24px_rgba(26,26,26,0.5)]">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F5F5F0] text-[#1A1A1A]">
              <Icon size={18} strokeWidth={1.8} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[#1A1A1A]">{title}</p>
              <p className="mt-1 text-xs text-[#8E8E93]">{subtitle}</p>
            </div>
            <span className="text-[#C7C7CC]">&rsaquo;</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MobileAppShowcase({ locale }: { locale: Locale }) {
  const [activeTabId, setActiveTabId] = useState<TabId>("today");
  const [browseSegment, setBrowseSegment] = useState<BrowseSegmentId>("history");
  const activeTab = appTabs.find((tab) => tab.id === activeTabId) ?? appTabs[0];

  return (
    <div className="bg-[radial-gradient(circle_at_top,#f7f4ea_0%,#fafaf8_45%,#ffffff_100%)]">
      <section className="mx-auto max-w-7xl px-6 pb-10 pt-14">
        <div className="max-w-3xl">
          <span className="inline-flex rounded-full border border-ink/10 bg-white/80 px-4 py-1.5 text-xs uppercase tracking-[0.28em] text-ink-light">
            {locale === "en" ? "Mobile App Prototype" : "移动端原型实现"}
          </span>
          <h1 className="mt-5 font-serif text-4xl leading-tight text-ink md:text-6xl">
            {locale === "en" ? "InkSight mobile, translated from spec into a browsable product prototype." : "把 InkSight 手机 App 设计文档，直接落成可浏览的产品原型。"}
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-8 text-ink-light md:text-lg">
            {locale === "en"
              ? "This page turns `docs/mobile-app-design.md` into a concrete experience: a centered 5-tab shell, 22 mapped screens, Lucide ink-stroke iconography, iOS-toned visuals, backend API expansion, and a phased delivery plan."
              : "这个页面把 `docs/mobile-app-design.md` 里的信息组织成真实界面：中心按钮 5-Tab、22 个页面映射、Lucide 墨感图标、米白纸张色系、后端扩展端点和四阶段实施路线图。"}
          </p>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          {[
            locale === "en" ? "12 spec chapters" : "12 章规格文档",
            locale === "en" ? "22 mapped screens" : "22 个页面映射",
            locale === "en" ? "Center-button 5-tab" : "中心按钮 5-Tab",
            locale === "en" ? "Lucide 1.8px icons" : "Lucide 1.8px 图标",
            locale === "en" ? "6 backend extensions" : "6 个后端扩展端点",
            locale === "en" ? "4 delivery phases" : "4 个实施阶段",
          ].map((item) => (
            <span key={item} className="rounded-full border border-ink/10 bg-white/90 px-4 py-2 text-sm text-ink">
              {item}
            </span>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link href={withLocalePath(locale, "/docs")}>
            <Button className="rounded-full px-6">{locale === "en" ? "Open Docs" : "查看文档中心"}</Button>
          </Link>
          <Link href={withLocalePath(locale, "/config")}>
            <Button variant="outline" className="rounded-full px-6">{locale === "en" ? "Open Device Config" : "查看设备配置"}</Button>
          </Link>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-8 px-6 pb-18 lg:grid-cols-[420px_minmax(0,1fr)]">
        <div className="lg:sticky lg:top-24 lg:self-start">
          <PhoneShell
            locale={locale}
            activeTab={activeTab}
            browseSegment={browseSegment}
            setBrowseSegment={setBrowseSegment}
            setActiveTab={setActiveTabId}
          />
        </div>

        <div className="space-y-6">
          <Card className="overflow-hidden rounded-[32px] border-[#e8e3d8] bg-white/90 shadow-[0_24px_70px_-48px_rgba(26,26,26,0.4)]">
            <CardHeader className="pb-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full border border-ink/10 bg-[#F5F5F0] px-3 py-1 text-xs uppercase tracking-[0.24em] text-ink-light">
                  {tr(locale, activeTab.eyebrow)}
                </span>
                {activeTab.metrics.map((metric) => (
                  <span key={metric.value + metric.label.zh} className="rounded-full border border-ink/10 px-3 py-1 text-xs text-ink-light">
                    {tr(locale, metric.label)} · {metric.value}
                  </span>
                ))}
              </div>
              <CardTitle className="mt-4 font-serif text-3xl text-ink">{tr(locale, activeTab.title)}</CardTitle>
              <CardDescription className="text-base leading-7 text-ink-light">{tr(locale, activeTab.summary)}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-4">
                <div className="rounded-[24px] border border-ink/10 bg-[#fafaf8] p-5">
                  <h3 className="font-serif text-xl text-ink">{locale === "en" ? "Screen stack" : "页面栈"}</h3>
                  <div className="mt-4 space-y-3">
                    {activeTab.screens.map((screen) => (
                      <div key={screen.name} className="rounded-[18px] border border-white bg-white px-4 py-3 shadow-sm">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-ink">{screen.name}</p>
                            <p className="mt-1 text-sm leading-6 text-ink-light">{tr(locale, screen.detail)}</p>
                          </div>
                          <span className="rounded-full bg-[#F5F5F0] px-3 py-1 text-[11px] text-ink-light">
                            {screen.api.length}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {screen.api.map((api) => (
                            <code key={api} className="rounded-full border border-ink/10 bg-white px-3 py-1 text-[11px] text-ink">
                              {api}
                            </code>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[24px] border border-ink/10 bg-white p-5">
                  <h3 className="font-serif text-xl text-ink">{locale === "en" ? "Interaction notes" : "交互说明"}</h3>
                  <div className="mt-4 grid gap-3">
                    {activeTab.interactions.map((interaction) => (
                      <div key={interaction.zh} className="rounded-[18px] bg-[#F5F5F0] px-4 py-3 text-sm leading-6 text-ink-light">
                        {tr(locale, interaction)}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-[24px] border border-ink/10 bg-[#1A1A1A] p-5 text-white">
                  <h3 className="font-serif text-xl">{locale === "en" ? "API mapping" : "API 映射"}</h3>
                  <div className="mt-4 space-y-3">
                    {activeTab.apis.map((api) => (
                      <div key={api.path} className="rounded-[18px] border border-white/10 bg-white/5 px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2 text-sm font-medium">
                            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] uppercase tracking-[0.18em]">
                              {api.method}
                            </span>
                            <code className="text-xs text-white/90">{api.path}</code>
                          </div>
                          {api.isNew ? (
                            <span className="rounded-full bg-[#34C759]/20 px-2 py-0.5 text-[11px] text-[#9df3b2]">
                              {locale === "en" ? "New" : "新增"}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-2 text-sm leading-6 text-white/75">{tr(locale, api.note)}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[24px] border border-ink/10 bg-[#fafaf8] p-5">
                  <h3 className="font-serif text-xl text-ink">{locale === "en" ? "Tab rationale" : "导航策略"}</h3>
                  <div className="mt-4 space-y-3 text-sm leading-6 text-ink-light">
                    <p>{locale === "en" ? "The centered create button turns UGC into a primary action without pushing device management out of the main shell." : "中间凸起的创作按钮让 UGC 成为一级入口，同时不挤压设备管理和首页沉浸阅读。"} </p>
                    <p>{locale === "en" ? "All tabs keep serif labels and 1.8px Lucide strokes to match the e-ink aesthetic." : "所有 Tab 保持衬线标签与 1.8px Lucide 描边，和墨水屏气质保持一致。"} </p>
                    <p>{locale === "en" ? "The shell is intentionally calm: fewer loud colors, no emoji, and a paper-first background." : "整体视觉故意克制：少量高饱和色、无 emoji、纸张感背景优先。"} </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <Card className="rounded-[32px] border-[#e8e3d8] bg-white/90">
              <CardHeader>
                <CardTitle className="font-serif text-2xl">{locale === "en" ? "Screen matrix" : "页面矩阵"}</CardTitle>
                <CardDescription className="leading-7">
                  {locale === "en" ? "22 mapped surfaces grouped by primary tab and shell role." : "按主 Tab 和壳层角色整理的 22 个页面，用来承接设计文档里的功能清单。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                {pageGroups.map((group) => (
                  <div key={group.group.zh} className="rounded-[22px] border border-ink/10 bg-[#fafaf8] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="font-serif text-lg text-ink">{tr(locale, group.group)}</h3>
                      <span className="rounded-full border border-ink/10 px-3 py-1 text-xs text-ink-light">{group.screens.length}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-ink-light">{tr(locale, group.description)}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {group.screens.map((screen) => (
                        <span key={screen} className="rounded-full bg-white px-3 py-1.5 text-xs text-ink">
                          {screen}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-[32px] border-[#e8e3d8] bg-white/90">
              <CardHeader>
                <CardTitle className="font-serif text-2xl">{locale === "en" ? "Design language" : "设计语言"}</CardTitle>
                <CardDescription className="leading-7">
                  {locale === "en" ? "A zen palette, Lucide icons, serif labels, and iOS-like structural rhythm." : "禅意简约色调、Lucide 图标、衬线标签和 iOS 式信息节奏，共同构成移动端视觉语言。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {colorTokens.map((token) => (
                    <div key={token.name} className="rounded-[20px] border border-ink/10 bg-[#fafaf8] p-3">
                      <div className="h-16 rounded-[14px] border border-black/5" style={{ backgroundColor: token.hex }} />
                      <p className="mt-3 text-sm font-medium text-ink">{token.name}</p>
                      <p className="mt-1 text-xs text-ink-light">{token.hex}</p>
                    </div>
                  ))}
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    { icon: Feather, title: locale === "en" ? "Ink-stroke icons" : "墨感图标", body: locale === "en" ? "Lucide, 1.8px stroke, no emoji." : "Lucide 统一图标，1.8px 描边，无 emoji。" },
                    { icon: Palette, title: locale === "en" ? "Paper-first surfaces" : "纸张质感", body: locale === "en" ? "Paper white, light surface contrast, restrained blue accents." : "米白纸张、浅表面对比、克制的 iOS 蓝点缀。" },
                    { icon: BookOpen, title: locale === "en" ? "Serif typography" : "衬线排版", body: locale === "en" ? "Noto Serif SC for content and tab labels, SF-style UI for metadata." : "内容与 Tab 标签偏衬线，元信息保持系统字体感。" },
                  ].map(({ icon: Icon, title, body }) => (
                    <div key={title} className="rounded-[22px] border border-ink/10 bg-[#fafaf8] p-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-ink shadow-sm">
                        <Icon size={18} strokeWidth={1.8} />
                      </div>
                      <p className="mt-4 text-base font-medium text-ink">{title}</p>
                      <p className="mt-2 text-sm leading-6 text-ink-light">{body}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            <Card className="rounded-[32px] border-[#e8e3d8] bg-white/90">
              <CardHeader>
                <CardTitle className="font-serif text-2xl">{locale === "en" ? "Backend expansion" : "后端扩展计划"}</CardTitle>
                <CardDescription className="leading-7">
                  {locale === "en" ? "Six focused endpoints cover push, preferences, structured content, and widget payloads." : "围绕推送、偏好、结构化内容和 widget 数据新增 6 个端点，尽量复用现有后端能力。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                {backendExtensions.map((item) => (
                  <div key={item.path} className="rounded-[22px] border border-ink/10 bg-[#fafaf8] p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-[#1A1A1A] px-2.5 py-1 text-[11px] uppercase tracking-[0.2em] text-white">{item.method}</span>
                      <code className="rounded-full border border-ink/10 bg-white px-3 py-1 text-xs text-ink">{item.path}</code>
                    </div>
                    <p className="mt-3 text-base font-medium text-ink">{tr(locale, item.title)}</p>
                    <p className="mt-2 text-sm leading-6 text-ink-light">{tr(locale, item.detail)}</p>
                  </div>
                ))}
                <div className="rounded-[22px] border border-dashed border-ink/15 bg-white p-4 text-sm leading-7 text-ink-light">
                  <strong className="text-ink">{locale === "en" ? "Database additions:" : "数据库扩展："}</strong>{" "}
                  {locale === "en"
                    ? "`push_tokens` stores user_id, token, platform, and timezone; `user_preferences` keeps push, widget mode, and locale."
                    : "`push_tokens` 用于存储 user_id、token、platform、timezone；`user_preferences` 负责 push、widget_mode、locale 等偏好。"}
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-[32px] border-[#e8e3d8] bg-white/90">
              <CardHeader>
                <CardTitle className="font-serif text-2xl">{locale === "en" ? "Delivery roadmap" : "实施路线图"}</CardTitle>
                <CardDescription className="leading-7">
                  {locale === "en" ? "Four phases move from Expo MVP to shipping polish without overloading the first release." : "用四个阶段把 Expo MVP、设备能力、移动端特性和发布打磨拆开，避免首版范围失控。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                {roadmap.map((phase, index) => (
                  <div key={phase.name} className="rounded-[22px] border border-ink/10 bg-[#fafaf8] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-base font-medium text-ink">{phase.name}</p>
                        <p className="mt-1 text-sm text-ink-light">{tr(locale, phase.duration)}</p>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-xs text-ink-light">0{index + 1}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-ink">{tr(locale, phase.focus)}</p>
                    <div className="mt-4 space-y-2">
                      {phase.tasks.map((task) => (
                        <div key={task.zh} className="rounded-[16px] bg-white px-3 py-2 text-sm leading-6 text-ink-light">
                          {tr(locale, task)}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}
