"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sparkles, Search, Download, Image as ImageIcon, Upload, Loader2, Check } from "lucide-react";
import { authHeaders } from "@/lib/auth";

// 分类列表
const categories = ["全部", "效率", "学习", "生活", "趣味", "极客"];

// 发布分类选项（不包含"全部"）
const publishCategories = ["效率", "学习", "生活", "趣味", "极客"];

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
  const fetchModes = async (category: string) => {
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
        throw new Error(`获取模式列表失败: ${response.status}`);
      }
      
      const data = await response.json();
      setModes(data.modes || []);
    } catch (err) {
      console.error("Failed to fetch modes:", err);
      setError(err instanceof Error ? err.message : "获取模式列表失败");
      setModes([]);
    } finally {
      setIsLoading(false);
    }
  };

  // 获取设备列表
  const fetchDevices = async () => {
    setIsLoadingDevices(true);
    try {
      const response = await fetch("/api/user/devices", {
        headers: authHeaders(),
      });
      
      if (!response.ok) {
        throw new Error(`获取设备列表失败: ${response.status}`);
      }
      
      const data = await response.json();
      setDevices(data.devices || []);
    } catch (err) {
      console.error("Failed to fetch devices:", err);
      setDevices([]);
    } finally {
      setIsLoadingDevices(false);
    }
  };

  // 获取用户自定义模式列表（按设备过滤）
  const fetchCustomModes = async (mac?: string) => {
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
        throw new Error(`获取自定义模式失败: ${response.status}`);
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
  };

  // 当分类改变时重新获取数据
  useEffect(() => {
    fetchModes(selectedCategory);
  }, [selectedCategory]);

  // 当打开发布弹窗时，获取设备列表和用户自定义模式列表
  useEffect(() => {
    if (isPublishModalOpen) {
      fetchDevices();
    }
  }, [isPublishModalOpen]);
  
  // 当选择设备时，获取该设备的自定义模式
  useEffect(() => {
    if (isPublishModalOpen && publishForm.mac) {
      fetchCustomModes(publishForm.mac);
    } else if (isPublishModalOpen && !publishForm.mac) {
      setCustomModes([]);
    }
  }, [isPublishModalOpen, publishForm.mac]);

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
        throw new Error(errorData.error || `安装失败: ${response.status}`);
      }

      const data = await response.json();
      
      // 标记为已安装
      setInstalledModes((prev) => new Set(prev).add(modeId));
      
      // 显示成功提示
      setToastMessage("成功添加至我的模式");
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
      
      console.log("Mode installed:", data.custom_mode_id);
    } catch (err) {
      console.error("Install failed:", err);
      setToastMessage(err instanceof Error ? err.message : "安装失败");
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
      setToastMessage("请填写所有必填项，包括选择设备");
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
    setPublishStatus("正在准备发布...");
    
    try {
      // 检查模式类型，如果是图片生成类型，提示用户
      const selectedMode = customModes.find(m => m.mode_id === publishForm.source_custom_mode_id);
      if (selectedMode) {
        setPublishStatus("正在生成预览图片，请稍候...");
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
        const errorMessage = errorData.error || `发布失败: ${response.status}`;
        
        // 如果是超时错误，给出更友好的提示
        if (response.status === 408) {
          throw new Error("图片生成超时，请检查图片生成 API 配置或稍后重试");
        }
        
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log("Published mode:", data);
      
      setPublishStatus("发布成功！");
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
      setToastMessage("发布成功！你的模式已分享到广场");
      setShowToast(true);
      setTimeout(() => setShowToast(false), 3000);
    } catch (error) {
      console.error("Publish failed:", error);
      setIsPublishing(false);
      setPublishStatus("");
      
      // 处理超时错误
      if (error instanceof Error && error.name === "AbortError") {
        setToastMessage("请求超时，图片生成可能需要更长时间。请稍后重试。");
      } else {
        setToastMessage(error instanceof Error ? error.message : "发布失败");
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
                探索社区模式
              </h1>
            </div>
            <p className="text-base md:text-lg text-ink-light mt-4 max-w-2xl mx-auto">
              发现、分享并安装由 InkSight 社区创造的个性化墨水屏应用。
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
                placeholder="搜索模式、作者或描述..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-300 rounded-sm text-ink placeholder:text-gray-400 focus:outline-none focus:border-black transition-colors"
              />
            </div>
          </div>

          {/* 分类标签和发布按钮 */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap justify-center gap-3 flex-1">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                    selectedCategory === category
                      ? "bg-ink text-white shadow-[2px_2px_0_0_#000000]"
                      : "bg-white text-ink hover:bg-gray-50 border border-gray-300 hover:border-black hover:shadow-[2px_2px_0_0_#000000]"
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
            <button
              onClick={() => setIsPublishModalOpen(true)}
              className="bg-ink text-white rounded-full px-4 py-1.5 text-sm font-medium flex items-center gap-2 hover:bg-ink/90 transition-colors"
            >
              <Upload size={16} />
              发布模式
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
              重试
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
                          <span className="text-xs text-gray-400">缩略图占位</span>
                        </div>
                      )}
                    </div>

                    {/* 描述 */}
                    <p className="text-sm text-gray-700 mb-4 flex-1 line-clamp-2 font-serif leading-relaxed">
                      {mode.description || "暂无描述"}
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
                            获取中...
                          </>
                        ) : isInstalled ? (
                          <>
                            <Check size={16} className="mr-2" />
                            已获取
                          </>
                        ) : (
                          <>
                            <Download size={16} className="mr-2" />
                            获取
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
            <p className="text-ink-light">暂无匹配的模式</p>
          </div>
        )}
      </section>

      {/* 发布弹窗 */}
      <Dialog open={isPublishModalOpen} onClose={() => setIsPublishModalOpen(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader onClose={() => setIsPublishModalOpen(false)}>
            <DialogTitle>发布模式到广场</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* 选择设备 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                选择设备 <span className="text-red-500">*</span>
              </label>
              {isLoadingDevices ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm flex items-center justify-center">
                  <Loader2 size={16} className="text-ink-light animate-spin" />
                  <span className="ml-2 text-sm text-ink-light">加载中...</span>
                </div>
              ) : devices.length === 0 ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink-light text-sm">
                  暂无设备，请先绑定设备
                </div>
              ) : (
                <select
                  value={publishForm.mac}
                  onChange={(e) => {
                    setPublishForm({ ...publishForm, mac: e.target.value, source_custom_mode_id: "" });
                  }}
                  className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink focus:outline-none focus:border-black transition-colors"
                >
                  <option value="">请选择设备</option>
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
                选择模式 <span className="text-red-500">*</span>
              </label>
              {isLoadingCustomModes ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm flex items-center justify-center">
                  <Loader2 size={16} className="text-ink-light animate-spin" />
                  <span className="ml-2 text-sm text-ink-light">加载中...</span>
                </div>
              ) : customModes.length === 0 ? (
                <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink-light text-sm">
                  暂无自定义模式，请先创建自定义模式
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
                  <option value="">请选择要分享的模式</option>
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
                展示名称 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={publishForm.name}
                onChange={(e) =>
                  setPublishForm({ ...publishForm, name: e.target.value })
                }
                placeholder="为你的模式起个名字"
                className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink placeholder:text-gray-400 focus:outline-none focus:border-black transition-colors"
              />
            </div>

            {/* 模式描述 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                模式描述
              </label>
              <textarea
                value={publishForm.description}
                onChange={(e) =>
                  setPublishForm({ ...publishForm, description: e.target.value })
                }
                placeholder="描述这个模式的特色和用途..."
                rows={4}
                className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink placeholder:text-gray-400 focus:outline-none focus:border-black transition-colors font-serif leading-relaxed resize-none"
              />
            </div>

            {/* 分类 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                分类 <span className="text-red-500">*</span>
              </label>
              <select
                value={publishForm.category}
                onChange={(e) =>
                  setPublishForm({ ...publishForm, category: e.target.value })
                }
                className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink focus:outline-none focus:border-black transition-colors"
              >
                <option value="">请选择分类</option>
                {publishCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
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
              取消
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
                  {publishStatus || "发布中..."}
                </>
              ) : (
                "确认发布"
              )}
            </Button>
            {isPublishing && publishStatus && (
              <div className="mt-3 text-center">
                <p className="text-xs text-ink-light">
                  {publishStatus}
                </p>
                {publishStatus.includes("图片生成") && (
                  <p className="text-xs text-ink-light mt-1">
                    正在等待图片生成完成，这可能需要几秒到几十秒，请耐心等待...
                  </p>
                )}
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
            <DialogTitle>选择安装设备</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {isLoadingDevices ? (
              <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm flex items-center justify-center">
                <Loader2 size={16} className="text-ink-light animate-spin" />
                <span className="ml-2 text-sm text-ink-light">加载中...</span>
              </div>
            ) : devices.length === 0 ? (
              <div className="w-full px-3 py-2 bg-white border border-gray-300 rounded-sm text-ink-light text-sm">
                暂无设备，请先绑定设备
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
              取消
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
