"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sparkles, Search, Download, Image as ImageIcon, Upload, Loader2, Check } from "lucide-react";
import { authHeaders } from "@/lib/auth";
import { localeFromPathname } from "@/lib/i18n";

const categoryOptions = [
  { value: "全部", zh: "全部", en: "All" },
  { value: "效率", zh: "效率", en: "Productivity" },
  { value: "学习", zh: "学习", en: "Learning" },
  { value: "生活", zh: "生活", en: "Life" },
  { value: "趣味", zh: "趣味", en: "Fun" },
  { value: "极客", zh: "极客", en: "Geek" },
];

const publishCategoryOptions = categoryOptions.filter((item) => item.value !== "全部");

// 模式数据类型
interface SharedMode {
  id: number;
  mode_id: string;
  name: string;
  description: string;
  category: string;
  thumbnail_url: string | null;
  created_at: string;
  author: string;
}

// 用户自定义模式类型
interface CustomMode {
  mode_id: string;
  display_name: string;
  description: string;
  source?: string;
}

// 设备类型
interface Device {
  mac: string;
  nickname: string;
  role: string;
  status: string;
}

export default function DiscoverPage() {
  const pathname = usePathname();
  const locale = localeFromPathname(pathname || "/");
  const isEn = locale === "en";
  const tr = useMemo(() => (zh: string, en: string) => (isEn ? en : zh), [isEn]);
  const [selectedCategory, setSelectedCategory] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string>(""); // 发布状态信息
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState("");
  
  // 数据状态
  const [modes, setModes] = useState<SharedMode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [installingModes, setInstallingModes] = useState<Set<number>>(new Set());
  const [installedModes, setInstalledModes] = useState<Set<number>>(new Set());
  
  // 用户自定义模式列表
  const [customModes, setCustomModes] = useState<CustomMode[]>([]);
  const [isLoadingCustomModes, setIsLoadingCustomModes] = useState(false);
  
  // 设备列表
  const [devices, setDevices] = useState<Device[]>([]);
  const [isLoadingDevices, setIsLoadingDevices] = useState(false);
  
  // 发布表单数据
  const [publishForm, setPublishForm] = useState({
    source_custom_mode_id: "",
    name: "",
    description: "",
    category: "",
    mac: "", // 设备 MAC 地址
  });
  
  // 安装模式时的设备选择
  const [installDeviceModal, setInstallDeviceModal] = useState<{
    open: boolean;
    modeId: number | null;
  }>({ open: false, modeId: null });

  // 获取模式列表
  const fetchModes = useCallback(async (category: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (category && category !== "全部") {
        params.append("category", category);
      }
      params.append("page", "1");
      params.append("limit", "100"); // 获取足够多的数据

      const response = await fetch(`/api/discover/modes?${params.toString()}`);

      if (!response.ok) {
        throw new Error(isEn ? `Failed to fetch modes: ${response.status}` : `获取模式列表失败: ${response.status}`);
      }

      const data = await response.json();
      setModes(data.modes || []);
    } catch (err) {
      console.error("Failed to fetch modes:", err);
      setError(err instanceof Error ? err.message : tr("获取模式列表失败", "Failed to fetch modes"));
      setModes([]);
    } finally {
      setIsLoading(false);
    }
  }, [isEn, tr]);

  // 获取设备列表
  const fetchDevices = useCallback(async () => {
    setIsLoadingDevices(true);
    try {
      const response = await fetch("/api/user/devices", {
        headers: authHeaders(),
      });

      if (!response.ok) {
        throw new Error(isEn ? `Failed to fetch devices: ${response.status}` : `获取设备列表失败: ${response.status}`);
      }

      const data = await response.json();
      setDevices(data.devices || []);
    } catch (err) {
      console.error("Failed to fetch devices:", err);
      setDevices([]);
    } finally {
      setIsLoadingDevices(false);
    }
  }, [isEn]);

  // 获取用户自定义模式列表（按设备过滤）
  const fetchCustomModes = useCallback(async (mac?: string) => {
    setIsLoadingCustomModes(true);
    try {
      const params = new URLSearchParams();
      if (mac) {
        params.append("mac", mac);
      }

      const response = await fetch(`/api/modes?${params.toString()}`, {
        headers: authHeaders(),
      });

      if (!response.ok) {
        throw new Error(isEn ? `Failed to fetch custom modes: ${response.status}` : `获取自定义模式失败: ${response.status}`);
      }

      const data = await response.json();
      // 过滤出自定义模式（source === "custom"）
      const custom = (data.modes || []).filter(
        (mode: CustomMode) => mode.source === "custom"
      );
      setCustomModes(custom);
    } catch (err) {
      console.error("Failed to fetch custom modes:", err);
      setCustomModes([]);
    } finally {
      setIsLoadingCustomModes(false);
    }
  }, [isEn]);

  // 当分类改变时重新获取数据
  useEffect(() => {
    fetchModes(selectedCategory);
  }, [selectedCategory, fetchModes]);

  // 当打开发布弹窗时，获取设备列表和用户自定义模式列表
  useEffect(() => {
    if (isPublishModalOpen) {
      fetchDevices();
    }
  }, [isPublishModalOpen, fetchDevices]);

  // 当选择设备时，获取该设备的自定义模式
  useEffect(() => {
    if (isPublishModalOpen && publishForm.mac) {
      fetchCustomModes(publishForm.mac);
    } else if (isPublishModalOpen && !publishForm.mac) {
      setCustomModes([]);
    }
  }, [isPublishModalOpen, publishForm.mac, fetchCustomModes]);

  // 打开安装设备选择弹窗
  const handleInstallClick = (modeId: number) => {
    if (installingModes.has(modeId) || installedModes.has(modeId)) {
      return;
    }
    setInstallDeviceModal({ open: true, modeId });
    if (devices.length === 0) {
      fetchDevices();
    }
  };

  // 安装模式
  const handleInstall = async (modeId: number, mac: string) => {
    if (installingModes.has(modeId) || installedModes.has(modeId)) {
      return;
    }

    setInstallingModes((prev) => new Set(prev).add(modeId));
    setInstallDeviceModal({ open: false, modeId: null });

    try {
      const response = await fetch(`/api/discover/modes/${modeId}/install`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify({ mac }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || (isEn ? `Install failed: ${response.status}` : `安装失败: ${response.status}`));
      }

      const data = await response.json();
      
      // 标记为已安装
      setInstalledModes((prev) => new Set(prev).add(modeId));
      
      // 显示成功提示
      setToastMessage(tr("成功添加至我的模式", "Added to My Modes"));
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      
      console.log("Mode installed:", data.custom_mode_id);
    } catch (err) {
      console.error("Install failed:", err);
      setToastMessage(err instanceof Error ? err.message : tr("安装失败", "Install failed"));
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    } finally {
      setInstallingModes((prev) => {
        const next = new Set(prev);
        next.delete(modeId);
        return next;
      });
    }
  };

  // 处理发布
  const handlePublish = async () => {
    if (!publishForm.source_custom_mode_id || !publishForm.name || !publishForm.category || !publishForm.mac) {
      setToastMessage(tr("请填写所有必填项，包括选择设备", "Please complete all required fields, including the target device"));
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      return;
    }

    const payload = {
      source_custom_mode_id: publishForm.source_custom_mode_id,
      name: publishForm.name,
      description: publishForm.description,
      category: publishForm.category,
      mac: publishForm.mac,
      // 后端会自动生成预览图片，不需要传递 thumbnail_base64
    };

    setIsPublishing(true);
    setPublishStatus(tr("正在准备发布...", "Preparing your mode for publishing..."));
    
    try {
      // 检查模式类型，如果是图片生成类型，提示用户
      const selectedMode = customModes.find(m => m.mode_id === publishForm.source_custom_mode_id);
      if (selectedMode) {
        setPublishStatus(tr("正在生成预览图片，请稍候...", "Generating preview image, please wait..."));
      }

      // 设置较长的超时时间（30秒），因为图片生成可能需要较长时间
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒超时
      
      const response = await fetch("/api/discover/modes/publish", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.error || (isEn ? `Publish failed: ${response.status}` : `发布失败: ${response.status}`);
        
        // 如果是超时错误，给出更友好的提示
        if (response.status === 408) {
          throw new Error(tr("图片生成超时，请检查图片生成 API 配置或稍后重试", "Image generation timed out. Please check your image API configuration or try again later."));
        }
        
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log("Published mode:", data);
      
      setPublishStatus(tr("发布成功！", "Published successfully!"));
      setIsPublishing(false);
      setIsPublishModalOpen(false);
      
      // 重置表单
      setPublishForm({
        source_custom_mode_id: "",
        name: "",
        description: "",
        category: "",
        mac: "",
      });

      // 刷新模式列表
      await fetchModes(selectedCategory);
      
      // 显示成功提示
      setToastMessage(tr("发布成功！你的模式已分享到广场", "Published successfully! Your mode is now visible in the plaza."));
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    } catch (error) {
      console.error("Publish failed:", error);
      setIsPublishing(false);
      setPublishStatus("");
      
      // 处理超时错误
      if (error instanceof Error && error.name === "AbortError") {
        setToastMessage(tr("请求超时，图片生成可能需要更长时间。请稍后重试。", "Request timed out. Image generation may need more time. Please try again later."));
      } else {
        setToastMessage(error instanceof Error ? error.message : tr("发布失败", "Publish failed"));
      }
      
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    }
  };

  // 过滤模式（客户端搜索）
  const filteredModes = modes.filter((mode) => {
    const matchesSearch =
      searchQuery === "" ||
      mode.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (mode.description && mode.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      mode.author.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  return (
    <div className="min-h-screen bg-white">
      {/* Hero Header 区域 */}
      <section className="border-b border-ink/10 bg-white bg-[linear-gradient(to_right,#f0f0f0_1px,transparent_1px),linear-gradient(to_bottom,#f0f0f0_1px,transparent_1px)] bg-[size:24px_24px]">
        <div className="mx-auto max-w-6xl px-6 py-16 md:py-24">
          {/* 标题区域 */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-4">
              <Sparkles size={28} className="text-ink" />
              <h1 className="font-serif text-4xl md:text-5xl font-bold text-ink">
                {tr("探索社区模式", "Explore Community Modes")}
              </h1>
            </div>
            <p className="text-base md:text-lg text-ink-light mt-4 max-w-2xl mx-auto">
              {tr("发现、分享并安装由 InkSight 社区创造的个性化墨水屏应用。", "Discover, share, and install personalized e-ink modes created by the InkSight community.")}
            </p>
          </div>

          {/* 搜索框 */}
          <div className="max-w-2xl mx-auto mb-8">
            <div className="relative">
              <Search
                size={20}
                className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-light"
              />
              <input
                type="text"
                placeholder={tr("搜索模式、作者或描述...", "Search modes, authors, or descriptions...")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-sm text-ink placeholder:text-gray-400 focus:outline-none focus:border-black transition-colors"
              />
            </div>
          </div>

          {/* 分类标签和发布按钮 */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap justify-center gap-3 flex-1">
              {categoryOptions.map((category) => (
                <button
                  key={category.value}
                  onClick={() => setSelectedCategory(category.value)}
                  className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                    selectedCategory === category.value
                      ? "bg-ink text-white shadow-[2px_2px_0_0_#000000]"
                      : "bg-white text-ink hover:bg-gray-50 border border-gray-300 hover:border-black hover:shadow-[2px_2px_0_0_#000000]"
                  }`}
                >
                  {isEn ? category.en : category.zh}
                </button>
              ))}
            </div>
            <button
              onClick={() => setIsPublishModalOpen(true)}
              className="bg-ink text-white rounded-full px-4 py-1.5 text-sm font-medium flex items-center gap-2 hover:bg-ink/90 transition-colors"
            >
              <Upload size={16} />
              {tr("发布模式", "Publish Mode")}
            </button>
          </div>
        </div>
      </section>

      {/* 模式网格区域 */}
      <section className="mx-auto max-w-6xl px-6 py-12 md:py-16">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={32} className="text-ink-light animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-16">
            <p className="text-ink-light mb-2">{error}</p>
            <button
              onClick={() => fetchModes(selectedCategory)}
              className="text-sm text-ink underline hover:text-ink/70"
            >
              {tr("重试", "Retry")}
            </button>
          </div>
        ) : filteredModes.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredModes.map((mode) => {
              const isInstalling = installingModes.has(mode.id);
              const isInstalled = installedModes.has(mode.id);
              
              return (
                <Card
                  key={mode.id}
                  className="group border border-gray-200 hover:border-black hover:shadow-[4px_4px_0_0_#000000] transition-all duration-200 flex flex-col"
                >
                  <CardContent className="pt-8 px-6 pb-6 flex flex-col flex-1">
                    {/* 头部：名称、作者、分类 */}
                    <div className="mb-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h3 className="font-semibold text-lg text-ink mb-1">
                            {mode.name}
                          </h3>
                          <p className="text-sm text-ink-light">{mode.author}</p>
                        </div>
                        <span className="px-2.5 py-1 text-xs font-medium text-ink bg-paper-dark rounded-sm whitespace-nowrap ml-3">
                          {mode.category}
                        </span>
                      </div>
                    </div>

                    {/* 缩略图 */}
                    <div className="w-full aspect-[4/3] mb-4 border border-gray-300 bg-white rounded-sm overflow-hidden relative">
                      {mode.thumbnail_url ? (
                        <Image
                          src={mode.thumbnail_url}
                          alt={mode.name}
                          fill
                          className="object-contain bg-white"
                          unoptimized
                        />
                      ) : (
                        <div className="w-full h-full border border-dashed border-gray-300 bg-white rounded-sm flex items-center justify-center flex-col">
                          <ImageIcon size={32} className="text-gray-400 mb-2" />
                          <span className="text-xs text-gray-400">{tr("缩略图占位", "Thumbnail placeholder")}</span>
                        </div>
                      )}
                    </div>

                    {/* 描述 */}
                    <p className="text-sm text-gray-700 mb-4 flex-1 line-clamp-2 font-serif leading-relaxed">
                      {mode.description || tr("暂无描述", "No description yet")}
                    </p>

                    {/* 底部操作区 */}
                    <div className="mt-auto pt-4 border-t border-ink/5">
                      <Button
                        variant="outline"
                        onClick={() => handleInstallClick(mode.id)}
                        disabled={isInstalling || isInstalled}
                        className={`w-full transition-colors ${
                          isInstalled
                            ? "bg-gray-100 text-gray-600 border-gray-300 cursor-not-allowed"
                            : "bg-white text-black border border-black hover:bg-black hover:text-white"
                        }`}
                      >
                        {isInstalling ? (
                          <>
                            <Loader2 size={16} className="mr-2 animate-spin" />
                            {tr("获取中...", "Installing...")}
                          </>
                        ) : isInstalled ? (
                          <>
                            <Check size={16} className="mr-2" />
                            {tr("已获取", "Installed")}
                          </>
                        ) : (
                          <>
                            <Download size={16} className="mr-2" />
                            {tr("获取", "Install")}
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-ink-light">{tr("暂无匹配的模式", "No matching modes yet")}</p>
          </div>
        )}
      </section>

      {/* 发布弹窗 */}
      <Dialog open={isPublishModalOpen} onClose={() => setIsPublishModalOpen(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader onClose={() => setIsPublishModalOpen(false)}>
            <DialogTitle>{tr("发布模式到广场", "Publish a Mode to the Plaza")}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* 选择设备 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                {tr("选择设备", "Select Device")} <span className="text-red-500">*</span>
              </label>
              {isLoadingDevices ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm flex items-center justify-center">
                  <Loader2 size={16} className="text-ink-light animate-spin" />
                  <span className="ml-2 text-sm text-ink-light">{tr("加载中...", "Loading...")}</span>
                </div>
              ) : devices.length === 0 ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink-light text-sm">
                  {tr("暂无设备，请先绑定设备", "No devices yet. Please bind a device first.")}
                </div>
              ) : (
                <select
                  value={publishForm.mac}
                  onChange={(e) => {
                    setPublishForm({ ...publishForm, mac: e.target.value, source_custom_mode_id: "" });
                  }}
                  className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink focus:outline-none focus:border-black transition-colors"
                >
                  <option value="">{tr("请选择设备", "Choose a device")}</option>
                  {devices.map((device) => (
                    <option key={device.mac} value={device.mac}>
                      {device.nickname || device.mac} ({device.mac})
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* 选择模式 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                {tr("选择模式", "Select Mode")} <span className="text-red-500">*</span>
              </label>
              {isLoadingCustomModes ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm flex items-center justify-center">
                  <Loader2 size={16} className="text-ink-light animate-spin" />
                  <span className="ml-2 text-sm text-ink-light">{tr("加载中...", "Loading...")}</span>
                </div>
              ) : customModes.length === 0 ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink-light text-sm">
                  {tr("暂无自定义模式，请先创建自定义模式", "No custom modes yet. Please create one first.")}
                </div>
              ) : (
                <select
                  value={publishForm.source_custom_mode_id}
                  onChange={(e) => {
                    const selectedMode = customModes.find(
                      (m) => m.mode_id === e.target.value
                    );
                    setPublishForm({
                      ...publishForm,
                      source_custom_mode_id: e.target.value,
                      name: selectedMode?.display_name || publishForm.name,
                      description: selectedMode?.description || publishForm.description,
                    });
                  }}
                  className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink focus:outline-none focus:border-black transition-colors"
                >
                  <option value="">{tr("请选择要分享的模式", "Choose a mode to share")}</option>
                  {customModes.map((mode) => (
                    <option key={mode.mode_id} value={mode.mode_id}>
                      {mode.mode_id}: {mode.display_name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* 展示名称 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                {tr("展示名称", "Display Name")} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={publishForm.name}
                onChange={(e) =>
                  setPublishForm({ ...publishForm, name: e.target.value })
                }
                placeholder={tr("为你的模式起个名字", "Give your mode a memorable name")}
                className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink placeholder:text-gray-400 focus:outline-none focus:border-black transition-colors"
              />
            </div>

            {/* 模式描述 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                {tr("模式描述", "Description")}
              </label>
              <textarea
                value={publishForm.description}
                onChange={(e) =>
                  setPublishForm({ ...publishForm, description: e.target.value })
                }
                placeholder={tr("描述这个模式的特色和用途...", "Describe what this mode is for and what makes it special...")}
                rows={4}
                className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink placeholder:text-gray-400 focus:outline-none focus:border-black transition-colors font-serif leading-relaxed resize-none"
              />
            </div>

            {/* 分类 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                {tr("分类", "Category")} <span className="text-red-500">*</span>
              </label>
              <select
                value={publishForm.category}
                onChange={(e) =>
                  setPublishForm({ ...publishForm, category: e.target.value })
                }
                className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink focus:outline-none focus:border-black transition-colors"
              >
                <option value="">{tr("请选择分类", "Choose a category")}</option>
                {publishCategoryOptions.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {isEn ? cat.en : cat.zh}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* 底部操作按钮 */}
          <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-ink/10">
            <Button
              variant="outline"
              onClick={() => setIsPublishModalOpen(false)}
              disabled={isPublishing}
              className="bg-white text-black border border-black hover:bg-black hover:text-white transition-colors"
            >
              {tr("取消", "Cancel")}
            </Button>
            <Button
              onClick={handlePublish}
              disabled={
                isPublishing ||
                !publishForm.source_custom_mode_id ||
                !publishForm.name ||
                !publishForm.category
              }
              className="bg-ink text-white hover:bg-ink/90 transition-colors"
            >
              {isPublishing ? (
                <>
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  {publishStatus || tr("发布中...", "Publishing...")}
                </>
              ) : (
                tr("确认发布", "Confirm Publish")
              )}
            </Button>
            {isPublishing && publishStatus && (
              <div className="mt-3 text-center">
                <p className="text-xs text-ink-light">
                  {publishStatus}
                </p>
                {publishStatus.includes("图片生成") || publishStatus.includes("preview image") ? (
                  <p className="text-xs text-ink-light mt-1">
                    {tr("正在等待图片生成完成，这可能需要几秒到几十秒，请耐心等待...", "Waiting for image generation. This may take a few seconds to tens of seconds. Please hang tight...")}
                  </p>
                ) : null}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* 安装设备选择弹窗 */}
      <Dialog
        open={installDeviceModal.open}
        onClose={() => setInstallDeviceModal({ open: false, modeId: null })}
      >
        <DialogContent className="max-w-md">
          <DialogHeader onClose={() => setInstallDeviceModal({ open: false, modeId: null })}>
            <DialogTitle>{tr("选择安装设备", "Choose a Device to Install")}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {isLoadingDevices ? (
              <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm flex items-center justify-center">
                <Loader2 size={16} className="text-ink-light animate-spin" />
                <span className="ml-2 text-sm text-ink-light">{tr("加载中...", "Loading...")}</span>
              </div>
            ) : devices.length === 0 ? (
              <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink-light text-sm">
                {tr("暂无设备，请先绑定设备", "No devices yet. Please bind a device first.")}
              </div>
            ) : (
              <div className="space-y-2">
                {devices.map((device) => (
                  <button
                    key={device.mac}
                    onClick={() => {
                      if (installDeviceModal.modeId !== null) {
                        handleInstall(installDeviceModal.modeId, device.mac);
                      }
                    }}
                    className="w-full px-4 py-3 bg-white border border-gray-300 rounded-sm text-left hover:border-black hover:shadow-[2px_2px_0_0_#000000] transition-all"
                  >
                    <div className="font-medium text-ink">{device.nickname || device.mac}</div>
                    <div className="text-sm text-ink-light mt-1">{device.mac}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 底部操作按钮 */}
          <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-ink/10">
            <Button
              variant="outline"
              onClick={() => setInstallDeviceModal({ open: false, modeId: null })}
              className="bg-white text-black border border-black hover:bg-black hover:text-white transition-colors"
            >
              {tr("取消", "Cancel")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Toast 提示 */}
      {showToast && (
        <div className="fixed bottom-6 right-6 z-50 bg-ink text-white px-4 py-3 rounded-sm shadow-[4px_4px_0_0_#000000] animate-fade-in">
          <p className="text-sm">{toastMessage}</p>
        </div>
      )}
    </div>
  );
}
