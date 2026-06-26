import { useState, useEffect, useCallback } from 'react'
import {
  Wifi, RefreshCw, Plus, Search, Trash2, Edit2, Eye, Power, PowerOff,
  ChevronLeft, ChevronRight, Server, Link2, ShoppingCart, BookOpen, FolderSync,
} from 'lucide-react'
import {
  getChargePlatformConfigs,
  deleteChargePlatformConfig,
  updateChargePlatformConfig,
  getChargeSkuMappings,
  deleteChargeSkuMapping,
  getChargeOrders,
  listRecipes,
  deleteRecipe,
  type ChargePlatformConfig,
  type ChargePlatformStatus,
  type ChargeSkuMapping,
  type ChargeOrder,
  type ChargeOrderStatus,
  type ChargeSkuRecipe,
} from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'
import { useAuthStore } from '@/store/authStore'
import { PageLoading } from '@/components/common/Loading'
import { ConfirmModal } from '@/components/common/ConfirmModal'
import { ChargePlatformConfigFormModal } from './ChargePlatformConfigFormModal'
import { ChargeSkuMappingFormModal } from './ChargeSkuMappingFormModal'
import { ChargeOrderDetailModal } from './ChargeOrderDetailModal'
import { ChargeSkuRecipeFormModal } from './ChargeSkuRecipeFormModal'
import { ChargeSyncDialog } from './ChargeSyncDialog'

type TabKey = 'configs' | 'recipes' | 'mappings' | 'orders'

const tabs: Array<{ key: TabKey; label: string; icon: React.ElementType }> = [
  { key: 'configs', label: '平台账号', icon: Server },
  { key: 'recipes', label: '代刷配方', icon: BookOpen },
  { key: 'mappings', label: '套餐映射(P1 旧版)', icon: Link2 },
  { key: 'orders', label: '订单记录', icon: ShoppingCart },
]

const configStatusLabels: Record<ChargePlatformStatus, string> = {
  active: '正常',
  disabled: '已禁用',
  risk_controlled: '风控中',
  login_failed: '登录失败',
  balance_low: '余额不足',
}

const configStatusBadge: Record<ChargePlatformStatus, string> = {
  active: 'badge-success',
  disabled: 'badge-gray',
  risk_controlled: 'badge-danger',
  login_failed: 'badge-danger',
  balance_low: 'badge-warning',
}

const orderStatusLabels: Record<ChargeOrderStatus, string> = {
  pending: '待处理',
  collecting: '收集中',
  ready: '待下单',
  ordering: '下单中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

const orderStatusBadge: Record<ChargeOrderStatus, string> = {
  pending: 'badge-gray',
  collecting: 'badge-info',
  ready: 'badge-warning',
  ordering: 'badge-info',
  success: 'badge-success',
  failed: 'badge-danger',
  cancelled: 'badge-gray',
}

function Pagination({ page, totalPages, total, pageSize, onPageChange, onPageSizeChange }: {
  page: number
  totalPages: number
  total: number
  pageSize: number
  onPageChange: (p: number) => void
  onPageSizeChange: (s: number) => void
}) {
  if (total <= 0) return null
  return (
    <div className="flex-shrink-0 flex flex-col sm:flex-row items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700 gap-3">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span>每页</span>
        <select
          value={pageSize}
          onChange={e => onPageSizeChange(Number(e.target.value))}
          className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
        <span>条，共 {total} 条</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">第 {page} / {totalPages || 1} 页</span>
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}

export function ChargePlatforms() {
  const { addToast } = useUIStore()
  const { isAuthenticated, token, _hasHydrated } = useAuthStore()
  const [activeTab, setActiveTab] = useState<TabKey>('configs')
  const [loading, setLoading] = useState(true)

  const [configs, setConfigs] = useState<ChargePlatformConfig[]>([])
  const [configTotal, setConfigTotal] = useState(0)
  const [configPage, setConfigPage] = useState(1)
  const [configPageSize, setConfigPageSize] = useState(20)
  const [configSearch, setConfigSearch] = useState('')
  const [configFormModal, setConfigFormModal] = useState<{ open: boolean; config: ChargePlatformConfig | null }>({ open: false, config: null })
  const [configDeleteConfirm, setConfigDeleteConfirm] = useState<{ open: boolean; config: ChargePlatformConfig | null }>({ open: false, config: null })

  const [mappings, setMappings] = useState<ChargeSkuMapping[]>([])
  const [mappingTotal, setMappingTotal] = useState(0)
  const [mappingPage, setMappingPage] = useState(1)
  const [mappingPageSize, setMappingPageSize] = useState(20)
  const [mappingItemFilter, setMappingItemFilter] = useState('')
  const [mappingConfigFilter, setMappingConfigFilter] = useState('')
  const [mappingFormModal, setMappingFormModal] = useState<{ open: boolean; mapping: ChargeSkuMapping | null }>({ open: false, mapping: null })
  const [mappingDeleteConfirm, setMappingDeleteConfirm] = useState<{ open: boolean; mapping: ChargeSkuMapping | null }>({ open: false, mapping: null })

  const [orders, setOrders] = useState<ChargeOrder[]>([])
  const [orderTotal, setOrderTotal] = useState(0)
  const [orderPage, setOrderPage] = useState(1)
  const [orderPageSize, setOrderPageSize] = useState(20)
  const [orderStatusFilter, setOrderStatusFilter] = useState('')
  const [orderNoFilter, setOrderNoFilter] = useState('')
  const [orderDetail, setOrderDetail] = useState<ChargeOrder | null>(null)

  const [recipes, setRecipes] = useState<ChargeSkuRecipe[]>([])
  const [recipeTotal, setRecipeTotal] = useState(0)
  const [recipePage, setRecipePage] = useState(1)
  const [recipePageSize, setRecipePageSize] = useState(20)
  const [recipeItemFilter, setRecipeItemFilter] = useState('')
  const [recipeConfigFilter, setRecipeConfigFilter] = useState('')
  const [recipeFormModal, setRecipeFormModal] = useState<{ open: boolean; recipeId: number | null }>({ open: false, recipeId: null })
  const [recipeDeleteConfirm, setRecipeDeleteConfirm] = useState<{ open: boolean; recipe: ChargeSkuRecipe | null }>({ open: false, recipe: null })
  const [syncDialogConfig, setSyncDialogConfig] = useState<ChargePlatformConfig | null>(null)

  const loadConfigs = useCallback(async (p?: number, ps?: number, s?: string) => {
    if (!_hasHydrated || !isAuthenticated || !token) return
    const pg = p ?? configPage
    const sz = ps ?? configPageSize
    const sr = s ?? configSearch
    try {
      setLoading(true)
      const res = await getChargePlatformConfigs({ page: pg, page_size: sz, search: sr || undefined })
      setConfigs(res.items || [])
      setConfigTotal(res.total || 0)
    } catch {
      addToast({ type: 'error', message: '加载平台账号列表失败' })
    } finally {
      setLoading(false)
    }
  }, [_hasHydrated, isAuthenticated, token, configPage, configPageSize, configSearch, addToast])

  const loadMappings = useCallback(async (p?: number, ps?: number) => {
    if (!_hasHydrated || !isAuthenticated || !token) return
    const pg = p ?? mappingPage
    const sz = ps ?? mappingPageSize
    try {
      setLoading(true)
      const res = await getChargeSkuMappings({
        page: pg,
        page_size: sz,
        item_id: mappingItemFilter || undefined,
        platform_config_id: mappingConfigFilter ? Number(mappingConfigFilter) : undefined,
      })
      setMappings(res.items || [])
      setMappingTotal(res.total || 0)
    } catch {
      addToast({ type: 'error', message: '加载套餐映射列表失败' })
    } finally {
      setLoading(false)
    }
  }, [_hasHydrated, isAuthenticated, token, mappingPage, mappingPageSize, mappingItemFilter, mappingConfigFilter, addToast])

  const loadOrders = useCallback(async (p?: number, ps?: number) => {
    if (!_hasHydrated || !isAuthenticated || !token) return
    const pg = p ?? orderPage
    const sz = ps ?? orderPageSize
    try {
      setLoading(true)
      const res = await getChargeOrders({
        page: pg,
        page_size: sz,
        status: orderStatusFilter || undefined,
        xy_order_no: orderNoFilter || undefined,
      })
      setOrders(res.items || [])
      setOrderTotal(res.total || 0)
    } catch {
      addToast({ type: 'error', message: '加载订单列表失败' })
    } finally {
      setLoading(false)
    }
  }, [_hasHydrated, isAuthenticated, token, orderPage, orderPageSize, orderStatusFilter, orderNoFilter, addToast])

  const loadRecipes = useCallback(async (p?: number, ps?: number) => {
    if (!_hasHydrated || !isAuthenticated || !token) return
    const pg = p ?? recipePage
    const sz = ps ?? recipePageSize
    try {
      setLoading(true)
      const res = await listRecipes({
        page: pg,
        page_size: sz,
        item_id: recipeItemFilter || undefined,
        platform_config_id: recipeConfigFilter ? Number(recipeConfigFilter) : undefined,
      })
      setRecipes(res.items || [])
      setRecipeTotal(res.total || 0)
    } catch {
      addToast({ type: 'error', message: '加载配方列表失败' })
    } finally {
      setLoading(false)
    }
  }, [_hasHydrated, isAuthenticated, token, recipePage, recipePageSize, recipeItemFilter, recipeConfigFilter, addToast])

  useEffect(() => {
    if (activeTab === 'configs') loadConfigs()
    else if (activeTab === 'recipes') loadRecipes()
    else if (activeTab === 'mappings') loadMappings()
    else loadOrders()
  }, [activeTab, _hasHydrated, isAuthenticated, token])

  useEffect(() => {
    if (activeTab !== 'configs') return
    const t = setTimeout(() => { setConfigPage(1); loadConfigs(1, configPageSize, configSearch) }, 300)
    return () => clearTimeout(t)
  }, [configSearch])

  useEffect(() => {
    if (activeTab !== 'mappings') return
    const t = setTimeout(() => { setMappingPage(1); loadMappings(1, mappingPageSize) }, 300)
    return () => clearTimeout(t)
  }, [mappingItemFilter, mappingConfigFilter])

  useEffect(() => {
    if (activeTab !== 'orders') return
    const t = setTimeout(() => { setOrderPage(1); loadOrders(1, orderPageSize) }, 300)
    return () => clearTimeout(t)
  }, [orderStatusFilter, orderNoFilter])

  useEffect(() => {
    if (activeTab !== 'recipes') return
    const t = setTimeout(() => { setRecipePage(1); loadRecipes(1, recipePageSize) }, 300)
    return () => clearTimeout(t)
  }, [recipeItemFilter, recipeConfigFilter])

  const handleToggleConfigEnabled = async (config: ChargePlatformConfig) => {
    try {
      await updateChargePlatformConfig(config.id, { enabled: !config.enabled })
      addToast({ type: 'success', message: `已${config.enabled ? '禁用' : '启用'}` })
      loadConfigs()
    } catch {
      addToast({ type: 'error', message: '操作失败' })
    }
  }

  const handleDeleteConfig = async () => {
    if (!configDeleteConfirm.config) return
    try {
      await deleteChargePlatformConfig(configDeleteConfirm.config.id)
      addToast({ type: 'success', message: '已删除' })
      setConfigDeleteConfirm({ open: false, config: null })
      loadConfigs()
    } catch {
      addToast({ type: 'error', message: '删除失败' })
    }
  }

  const handleDeleteMapping = async () => {
    if (!mappingDeleteConfirm.mapping) return
    try {
      await deleteChargeSkuMapping(mappingDeleteConfirm.mapping.id)
      addToast({ type: 'success', message: '已删除' })
      setMappingDeleteConfirm({ open: false, mapping: null })
      loadMappings()
    } catch {
      addToast({ type: 'error', message: '删除失败' })
    }
  }

  const handleDeleteRecipe = async () => {
    if (!recipeDeleteConfirm.recipe) return
    try {
      await deleteRecipe(recipeDeleteConfirm.recipe.id)
      addToast({ type: 'success', message: '已删除' })
      setRecipeDeleteConfirm({ open: false, recipe: null })
      loadRecipes()
    } catch {
      addToast({ type: 'error', message: '删除失败' })
    }
  }

  const configTotalPages = Math.ceil(configTotal / configPageSize) || 1
  const recipeTotalPages = Math.ceil(recipeTotal / recipePageSize) || 1
  const mappingTotalPages = Math.ceil(mappingTotal / mappingPageSize) || 1
  const orderTotalPages = Math.ceil(orderTotal / orderPageSize) || 1

  const fmt = (dt: string | null) => dt ? new Date(dt).toLocaleString('zh-CN') : '-'

  if (loading && configs.length === 0 && recipes.length === 0 && mappings.length === 0 && orders.length === 0) {
    return <PageLoading />
  }

  return (
    <div className="space-y-4">
      <div className="page-header flex-between flex-wrap gap-4">
        <div>
          <h1 className="page-title">流量充值</h1>
          <p className="page-description">管理充值平台账号、套餐映射与代下单订单</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {activeTab === 'configs' && (
            <button onClick={() => setConfigFormModal({ open: true, config: null })} className="btn-ios-primary">
              <Plus className="w-4 h-4" />
              新建账号
            </button>
          )}
          {activeTab === 'recipes' && (
            <button onClick={() => setRecipeFormModal({ open: true, recipeId: null })} className="btn-ios-primary">
              <Plus className="w-4 h-4" />
              新建配方
            </button>
          )}
          {activeTab === 'mappings' && (
            <button onClick={() => setMappingFormModal({ open: true, mapping: null })} className="btn-ios-primary">
              <Plus className="w-4 h-4" />
              新建映射
            </button>
          )}
          <button
            onClick={() => {
              if (activeTab === 'configs') loadConfigs()
              else if (activeTab === 'recipes') loadRecipes()
              else if (activeTab === 'mappings') loadMappings()
              else loadOrders()
            }}
            className="btn-ios-secondary"
          >
            <RefreshCw className="w-4 h-4" />
            刷新
          </button>
        </div>
      </div>

      <div className="vben-card">
        <div className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex">
            {tabs.map(tab => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.key
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {activeTab === 'configs' && (
        <>
          <div className="vben-card">
            <div className="vben-card-body">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="input-group">
                  <label className="input-label">搜索</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={configSearch}
                      onChange={e => setConfigSearch(e.target.value)}
                      placeholder="搜索账号别名或用户名..."
                      className="input-ios pl-9"
                    />
                  </div>
                </div>
              </div>
              {configSearch && (
                <div className="mt-3 flex justify-end">
                  <button onClick={() => setConfigSearch('')} className="btn-ios-secondary btn-sm text-red-500">重置筛选</button>
                </div>
              )}
            </div>
          </div>

          <div className="vben-card flex flex-col" style={{ height: 'calc(100vh - 360px)', minHeight: '400px' }}>
            <div className="vben-card-header flex-shrink-0">
              <h2 className="vben-card-title">
                <Wifi className="w-4 h-4" />
                平台账号列表
              </h2>
              <span className="badge-primary">{configTotal} 个账号</span>
            </div>
            <div className="flex-1 overflow-auto">
              {loading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : (
                <table className="table-ios min-w-[900px]">
                  <thead className="sticky top-0 bg-white dark:bg-slate-800 z-10">
                    <tr>
                      <th className="whitespace-nowrap w-16">ID</th>
                      <th className="whitespace-nowrap min-w-[120px]">别名</th>
                      <th className="whitespace-nowrap min-w-[100px]">用户名</th>
                      <th className="whitespace-nowrap">余额</th>
                      <th className="whitespace-nowrap">状态</th>
                      <th className="whitespace-nowrap">启用</th>
                      <th className="whitespace-nowrap">限速</th>
                      <th className="whitespace-nowrap">最后错误</th>
                      <th className="whitespace-nowrap">更新时间</th>
                      <th className="whitespace-nowrap sticky right-0 bg-slate-50 dark:bg-slate-800">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {configs.length === 0 ? (
                      <tr>
                        <td colSpan={10}>
                          <div className="empty-state py-8">
                            <Wifi className="empty-state-icon" />
                            <p className="text-gray-500">{configSearch ? '没有匹配的账号' : '暂无平台账号'}</p>
                          </div>
                        </td>
                      </tr>
                    ) : configs.map(c => (
                      <tr key={c.id}>
                        <td className="text-xs text-gray-500">{c.id}</td>
                        <td>
                          <span className="font-medium text-slate-900 dark:text-slate-100">{c.name}</span>
                          {c.remark && (
                            <span className="block text-[11px] text-slate-500 dark:text-slate-400 truncate max-w-[180px]" title={c.remark}>
                              {c.remark}
                            </span>
                          )}
                        </td>
                        <td className="text-sm">{c.username}</td>
                        <td>
                          <span className={`text-sm font-medium ${Number(c.balance) <= Number(c.balance_alert_threshold) ? 'text-red-500' : 'text-green-600 dark:text-green-400'}`}>
                            ¥{c.balance}
                          </span>
                        </td>
                        <td>
                          <span className={`${configStatusBadge[c.status]} text-xs`}>
                            {configStatusLabels[c.status]}
                          </span>
                        </td>
                        <td>
                          {c.enabled
                            ? <span className="badge-success text-xs">启用</span>
                            : <span className="badge-gray text-xs">禁用</span>
                          }
                        </td>
                        <td className="text-xs text-gray-500">{c.max_orders_per_hour}/h</td>
                        <td className="max-w-[160px]">
                          {c.last_error ? (
                            <span className="text-xs text-red-500 truncate block" title={c.last_error}>{c.last_error}</span>
                          ) : (
                            <span className="text-xs text-gray-400">-</span>
                          )}
                        </td>
                        <td className="text-[11px] text-gray-500 whitespace-nowrap">{fmt(c.updated_at)}</td>
                        <td className="sticky right-0 bg-white dark:bg-slate-900">
                          <div className="flex gap-1">
                            <button
                              onClick={() => setConfigFormModal({ open: true, config: c })}
                              className="table-action-btn hover:!bg-blue-50"
                              title="编辑"
                            >
                              <Edit2 className="w-4 h-4 text-blue-500" />
                            </button>
                            <button
                              onClick={() => handleToggleConfigEnabled(c)}
                              className="table-action-btn hover:!bg-blue-50"
                              title={c.enabled ? '禁用' : '启用'}
                            >
                              {c.enabled
                                ? <Power className="w-4 h-4 text-green-500" />
                                : <PowerOff className="w-4 h-4 text-gray-400" />
                              }
                            </button>
                            <button
                              onClick={() => setSyncDialogConfig(c)}
                              className="table-action-btn hover:!bg-blue-50"
                              title="立即同步"
                            >
                              <FolderSync className="w-4 h-4 text-blue-500" />
                            </button>
                            <button
                              onClick={() => setConfigDeleteConfirm({ open: true, config: c })}
                              className="table-action-btn hover:!bg-red-50"
                              title="删除"
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <Pagination
              page={configPage}
              totalPages={configTotalPages}
              total={configTotal}
              pageSize={configPageSize}
              onPageChange={p => { setConfigPage(p); loadConfigs(p) }}
              onPageSizeChange={s => { setConfigPageSize(s); setConfigPage(1); loadConfigs(1, s) }}
            />
          </div>
        </>
      )}

      {activeTab === 'recipes' && (
        <>
          <div className="vben-card">
            <div className="vben-card-body">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="input-group">
                  <label className="input-label">商品ID</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={recipeItemFilter}
                      onChange={e => setRecipeItemFilter(e.target.value)}
                      placeholder="按闲鱼商品ID筛选..."
                      className="input-ios pl-9"
                    />
                  </div>
                </div>
                <div className="input-group">
                  <label className="input-label">平台账号</label>
                  <select
                    value={recipeConfigFilter}
                    onChange={e => setRecipeConfigFilter(e.target.value)}
                    className="input-ios"
                  >
                    <option value="">全部</option>
                    {configs.map(c => (
                      <option key={c.id} value={String(c.id)}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              {(recipeItemFilter || recipeConfigFilter) && (
                <div className="mt-3 flex justify-end">
                  <button onClick={() => { setRecipeItemFilter(''); setRecipeConfigFilter('') }} className="btn-ios-secondary btn-sm text-red-500">重置筛选</button>
                </div>
              )}
            </div>
          </div>

          <div className="vben-card flex flex-col" style={{ height: 'calc(100vh - 360px)', minHeight: '400px' }}>
            <div className="vben-card-header flex-shrink-0">
              <h2 className="vben-card-title">
                <BookOpen className="w-4 h-4" />
                配方列表
              </h2>
              <span className="badge-primary">{recipeTotal} 个配方</span>
            </div>
            <div className="flex-1 overflow-auto">
              {loading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : (
                <table className="table-ios min-w-[900px]">
                  <thead className="sticky top-0 bg-white dark:bg-slate-800 z-10">
                    <tr>
                      <th className="whitespace-nowrap w-16">ID</th>
                      <th className="whitespace-nowrap min-w-[120px]">配方名</th>
                      <th className="whitespace-nowrap min-w-[120px]">闲鱼商品ID</th>
                      <th className="whitespace-nowrap">规格</th>
                      <th className="whitespace-nowrap min-w-[100px]">平台账号</th>
                      <th className="whitespace-nowrap">子项</th>
                      <th className="whitespace-nowrap">状态</th>
                      <th className="whitespace-nowrap">更新时间</th>
                      <th className="whitespace-nowrap sticky right-0 bg-slate-50 dark:bg-slate-800">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recipes.length === 0 ? (
                      <tr>
                        <td colSpan={9}>
                          <div className="empty-state py-8">
                            <BookOpen className="empty-state-icon" />
                            <p className="text-gray-500">{recipeItemFilter || recipeConfigFilter ? '没有匹配的配方' : '暂无配方'}</p>
                          </div>
                        </td>
                      </tr>
                    ) : recipes.map(r => (
                      <tr key={r.id}>
                        <td className="text-xs text-gray-500">{r.id}</td>
                        <td>
                          <span className="font-medium text-slate-900 dark:text-slate-100">{r.name}</span>
                          {r.description && (
                            <span className="block text-[11px] text-slate-500 dark:text-slate-400 truncate max-w-[180px]" title={r.description}>
                              {r.description}
                            </span>
                          )}
                        </td>
                        <td>
                          <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">{r.item_id}</code>
                        </td>
                        <td className="text-sm">{r.spec_value || <span className="text-gray-400">全部</span>}</td>
                        <td className="text-sm">{r.platform_config_name || r.platform_config_id}</td>
                        <td>
                          <span className="badge-info text-xs">{(r.items || []).length} 项</span>
                        </td>
                        <td>
                          {r.is_active
                            ? <span className="badge-success text-xs">启用</span>
                            : <span className="badge-gray text-xs">禁用</span>
                          }
                        </td>
                        <td className="text-[11px] text-gray-500 whitespace-nowrap">{fmt(r.updated_at)}</td>
                        <td className="sticky right-0 bg-white dark:bg-slate-900">
                          <div className="flex gap-1">
                            <button
                              onClick={() => setRecipeFormModal({ open: true, recipeId: r.id })}
                              className="table-action-btn hover:!bg-blue-50"
                              title="编辑"
                            >
                              <Edit2 className="w-4 h-4 text-blue-500" />
                            </button>
                            <button
                              onClick={() => setRecipeDeleteConfirm({ open: true, recipe: r })}
                              className="table-action-btn hover:!bg-red-50"
                              title="删除"
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <Pagination
              page={recipePage}
              totalPages={recipeTotalPages}
              total={recipeTotal}
              pageSize={recipePageSize}
              onPageChange={p => { setRecipePage(p); loadRecipes(p) }}
              onPageSizeChange={s => { setRecipePageSize(s); setRecipePage(1); loadRecipes(1, s) }}
            />
          </div>
        </>
      )}

      {activeTab === 'mappings' && (
        <>
          <div className="vben-card">
            <div className="vben-card-body">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="input-group">
                  <label className="input-label">商品ID</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={mappingItemFilter}
                      onChange={e => setMappingItemFilter(e.target.value)}
                      placeholder="按闲鱼商品ID筛选..."
                      className="input-ios pl-9"
                    />
                  </div>
                </div>
                <div className="input-group">
                  <label className="input-label">平台账号</label>
                  <select
                    value={mappingConfigFilter}
                    onChange={e => setMappingConfigFilter(e.target.value)}
                    className="input-ios"
                  >
                    <option value="">全部</option>
                    {configs.map(c => (
                      <option key={c.id} value={String(c.id)}>{c.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              {(mappingItemFilter || mappingConfigFilter) && (
                <div className="mt-3 flex justify-end">
                  <button onClick={() => { setMappingItemFilter(''); setMappingConfigFilter('') }} className="btn-ios-secondary btn-sm text-red-500">重置筛选</button>
                </div>
              )}
            </div>
          </div>

          <div className="vben-card flex flex-col" style={{ height: 'calc(100vh - 360px)', minHeight: '400px' }}>
            <div className="vben-card-header flex-shrink-0">
              <h2 className="vben-card-title">
                <Link2 className="w-4 h-4" />
                套餐映射列表
              </h2>
              <span className="badge-primary">{mappingTotal} 条映射</span>
            </div>
            <div className="flex-1 overflow-auto">
              {loading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : (
                <table className="table-ios min-w-[800px]">
                  <thead className="sticky top-0 bg-white dark:bg-slate-800 z-10">
                    <tr>
                      <th className="whitespace-nowrap w-16">ID</th>
                      <th className="whitespace-nowrap min-w-[100px]">平台账号</th>
                      <th className="whitespace-nowrap min-w-[120px]">闲鱼商品ID</th>
                      <th className="whitespace-nowrap">规格值</th>
                      <th className="whitespace-nowrap min-w-[100px]">平台套餐ID</th>
                      <th className="whitespace-nowrap min-w-[100px]">套餐名称</th>
                      <th className="whitespace-nowrap">状态</th>
                      <th className="whitespace-nowrap">更新时间</th>
                      <th className="whitespace-nowrap sticky right-0 bg-slate-50 dark:bg-slate-800">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mappings.length === 0 ? (
                      <tr>
                        <td colSpan={9}>
                          <div className="empty-state py-8">
                            <Link2 className="empty-state-icon" />
                            <p className="text-gray-500">{mappingItemFilter || mappingConfigFilter ? '没有匹配的映射' : '暂无套餐映射'}</p>
                          </div>
                        </td>
                      </tr>
                    ) : mappings.map(m => (
                      <tr key={m.id}>
                        <td className="text-xs text-gray-500">{m.id}</td>
                        <td className="text-sm">{m.platform_config_name || m.platform_config_id}</td>
                        <td>
                          <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">{m.item_id}</code>
                        </td>
                        <td className="text-sm">{m.spec_value || <span className="text-gray-400">全部</span>}</td>
                        <td className="text-sm font-medium">{m.platform_sku_id}</td>
                        <td className="text-sm">{m.platform_sku_name || '-'}</td>
                        <td>
                          {m.is_active
                            ? <span className="badge-success text-xs">启用</span>
                            : <span className="badge-gray text-xs">禁用</span>
                          }
                        </td>
                        <td className="text-[11px] text-gray-500 whitespace-nowrap">{fmt(m.updated_at)}</td>
                        <td className="sticky right-0 bg-white dark:bg-slate-900">
                          <div className="flex gap-1">
                            <button
                              onClick={() => setMappingFormModal({ open: true, mapping: m })}
                              className="table-action-btn hover:!bg-blue-50"
                              title="编辑"
                            >
                              <Edit2 className="w-4 h-4 text-blue-500" />
                            </button>
                            <button
                              onClick={() => setMappingDeleteConfirm({ open: true, mapping: m })}
                              className="table-action-btn hover:!bg-red-50"
                              title="删除"
                            >
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <Pagination
              page={mappingPage}
              totalPages={mappingTotalPages}
              total={mappingTotal}
              pageSize={mappingPageSize}
              onPageChange={p => { setMappingPage(p); loadMappings(p) }}
              onPageSizeChange={s => { setMappingPageSize(s); setMappingPage(1); loadMappings(1, s) }}
            />
          </div>
        </>
      )}

      {activeTab === 'orders' && (
        <>
          <div className="vben-card">
            <div className="vben-card-body">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="input-group">
                  <label className="input-label">闲鱼订单号</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={orderNoFilter}
                      onChange={e => setOrderNoFilter(e.target.value)}
                      placeholder="按订单号搜索..."
                      className="input-ios pl-9"
                    />
                  </div>
                </div>
                <div className="input-group">
                  <label className="input-label">订单状态</label>
                  <select
                    value={orderStatusFilter}
                    onChange={e => setOrderStatusFilter(e.target.value)}
                    className="input-ios"
                  >
                    <option value="">全部</option>
                    <option value="pending">待处理</option>
                    <option value="collecting">收集中</option>
                    <option value="ready">待下单</option>
                    <option value="ordering">下单中</option>
                    <option value="success">成功</option>
                    <option value="failed">失败</option>
                    <option value="cancelled">已取消</option>
                  </select>
                </div>
              </div>
              {(orderNoFilter || orderStatusFilter) && (
                <div className="mt-3 flex justify-end">
                  <button onClick={() => { setOrderNoFilter(''); setOrderStatusFilter('') }} className="btn-ios-secondary btn-sm text-red-500">重置筛选</button>
                </div>
              )}
            </div>
          </div>

          <div className="vben-card flex flex-col" style={{ height: 'calc(100vh - 360px)', minHeight: '400px' }}>
            <div className="vben-card-header flex-shrink-0">
              <h2 className="vben-card-title">
                <ShoppingCart className="w-4 h-4" />
                订单记录
              </h2>
              <span className="badge-primary">{orderTotal} 条记录</span>
            </div>
            <div className="flex-1 overflow-auto">
              {loading ? (
                <div className="flex justify-center py-8">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : (
                <table className="table-ios min-w-[1000px]">
                  <thead className="sticky top-0 bg-white dark:bg-slate-800 z-10">
                    <tr>
                      <th className="whitespace-nowrap w-16">ID</th>
                      <th className="whitespace-nowrap min-w-[140px]">闲鱼订单号</th>
                      <th className="whitespace-nowrap">买家手机</th>
                      <th className="whitespace-nowrap">平台套餐</th>
                      <th className="whitespace-nowrap">平台订单号</th>
                      <th className="whitespace-nowrap">状态</th>
                      <th className="whitespace-nowrap">重试</th>
                      <th className="whitespace-nowrap">失败原因</th>
                      <th className="whitespace-nowrap">创建时间</th>
                      <th className="whitespace-nowrap sticky right-0 bg-slate-50 dark:bg-slate-800">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.length === 0 ? (
                      <tr>
                        <td colSpan={10}>
                          <div className="empty-state py-8">
                            <ShoppingCart className="empty-state-icon" />
                            <p className="text-gray-500">{orderNoFilter || orderStatusFilter ? '没有匹配的订单' : '暂无订单记录'}</p>
                          </div>
                        </td>
                      </tr>
                    ) : orders.map(o => (
                      <tr key={o.id}>
                        <td className="text-xs text-gray-500">{o.id}</td>
                        <td>
                          <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">{o.xy_order_no}</code>
                        </td>
                        <td className="text-sm">{o.buyer_phone || '-'}</td>
                        <td className="text-sm">{o.platform_sku_id}</td>
                        <td className="text-sm">{o.platform_order_id || '-'}</td>
                        <td>
                          <span className={`${orderStatusBadge[o.status]} text-xs`}>
                            {orderStatusLabels[o.status]}
                          </span>
                        </td>
                        <td className="text-xs text-gray-500">{o.retry_count}/{o.max_retries}</td>
                        <td className="max-w-[160px]">
                          {o.fail_reason ? (
                            <span className="text-xs text-red-500 truncate block" title={o.fail_reason}>{o.fail_reason}</span>
                          ) : (
                            <span className="text-xs text-gray-400">-</span>
                          )}
                        </td>
                        <td className="text-[11px] text-gray-500 whitespace-nowrap">{fmt(o.created_at)}</td>
                        <td className="sticky right-0 bg-white dark:bg-slate-900">
                          <div className="flex gap-1">
                            <button
                              onClick={() => setOrderDetail(o)}
                              className="table-action-btn hover:!bg-blue-50"
                              title="查看详情"
                            >
                              <Eye className="w-4 h-4 text-blue-500" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <Pagination
              page={orderPage}
              totalPages={orderTotalPages}
              total={orderTotal}
              pageSize={orderPageSize}
              onPageChange={p => { setOrderPage(p); loadOrders(p) }}
              onPageSizeChange={s => { setOrderPageSize(s); setOrderPage(1); loadOrders(1, s) }}
            />
          </div>
        </>
      )}

      {configFormModal.open && (
        <ChargePlatformConfigFormModal
          config={configFormModal.config}
          onClose={() => setConfigFormModal({ open: false, config: null })}
          onSaved={loadConfigs}
        />
      )}

      {mappingFormModal.open && (
        <ChargeSkuMappingFormModal
          mapping={mappingFormModal.mapping}
          onClose={() => setMappingFormModal({ open: false, mapping: null })}
          onSaved={loadMappings}
        />
      )}

      {orderDetail && (
        <ChargeOrderDetailModal
          order={orderDetail}
          onClose={() => setOrderDetail(null)}
          onRefresh={loadOrders}
        />
      )}

      <ConfirmModal
        isOpen={configDeleteConfirm.open}
        title="删除平台账号"
        message={`确定要删除账号"${configDeleteConfirm.config?.name}"吗？此操作不可恢复。`}
        onConfirm={handleDeleteConfig}
        onCancel={() => setConfigDeleteConfirm({ open: false, config: null })}
      />

      <ConfirmModal
        isOpen={mappingDeleteConfirm.open}
        title="删除套餐映射"
        message={`确定要删除此映射吗？此操作不可恢复。`}
        onConfirm={handleDeleteMapping}
        onCancel={() => setMappingDeleteConfirm({ open: false, mapping: null })}
      />

      {recipeFormModal.open && (
        <ChargeSkuRecipeFormModal
          recipeId={recipeFormModal.recipeId}
          onClose={() => setRecipeFormModal({ open: false, recipeId: null })}
          onSaved={loadRecipes}
        />
      )}

      {syncDialogConfig && (
        <ChargeSyncDialog
          configId={syncDialogConfig.id}
          configName={syncDialogConfig.name}
          onClose={() => setSyncDialogConfig(null)}
        />
      )}

      <ConfirmModal
        isOpen={recipeDeleteConfirm.open}
        title="删除配方"
        message={`确定要删除配方"${recipeDeleteConfirm.recipe?.name}"吗？此操作不可恢复。`}
        onConfirm={handleDeleteRecipe}
        onCancel={() => setRecipeDeleteConfirm({ open: false, recipe: null })}
      />
    </div>
  )
}
