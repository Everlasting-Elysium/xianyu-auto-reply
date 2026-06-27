import { useState } from 'react'
import { X, Loader2, RefreshCw, CheckCircle, FolderSync } from 'lucide-react'
import { triggerSync, type ChargeSyncResult } from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'
import { getApiErrorMessage } from '@/utils/request'

interface Props {
  configId: number
  configName: string
  onClose: () => void
}

export function ChargeSyncDialog({ configId, configName, onClose }: Props) {
  const { addToast } = useUIStore()
  const [syncCategories, setSyncCategories] = useState(true)
  const [syncGoods, setSyncGoods] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<ChargeSyncResult | null>(null)

  const handleSync = async () => {
    if (!syncCategories && !syncGoods) {
      addToast({ type: 'warning', message: '请至少勾选一项' })
      return
    }
    setSyncing(true)
    setResult(null)
    try {
      const res = await triggerSync(configId, {
        sync_categories: syncCategories,
        sync_goods: syncGoods,
      })
      setResult(res)
      addToast({ type: 'success', message: res.accepted ? '同步任务已提交，后台处理中' : '同步完成' })
    } catch (error) {
      addToast({ type: 'error', message: getApiErrorMessage(error, '同步失败，请重试') })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 70 }}>
      <div className="modal-content max-w-md">
        <div className="modal-header flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FolderSync className="w-5 h-5 text-blue-500" />
            同步 · {configName}
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        <div className="modal-body space-y-5">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            从平台拉取最新的分类和商品数据到本地仓库，耗时可能较长。
          </p>

          <div className="space-y-3">
            <label className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-500 cursor-pointer transition-colors">
              <input
                type="checkbox"
                checked={syncCategories}
                onChange={e => setSyncCategories(e.target.checked)}
                disabled={syncing}
                className="w-4 h-4 rounded border-gray-300"
              />
              <div>
                <span className="text-sm font-medium text-gray-900 dark:text-white">同步分类</span>
                <span className="block text-xs text-gray-500 dark:text-gray-400">拉取平台商品分类树</span>
              </div>
            </label>

            <label className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-blue-500 cursor-pointer transition-colors">
              <input
                type="checkbox"
                checked={syncGoods}
                onChange={e => setSyncGoods(e.target.checked)}
                disabled={syncing}
                className="w-4 h-4 rounded border-gray-300"
              />
              <div>
                <span className="text-sm font-medium text-gray-900 dark:text-white">同步商品</span>
                <span className="block text-xs text-gray-500 dark:text-gray-400">拉取平台全量商品列表（可能耗时较久）</span>
              </div>
            </label>
          </div>

          {syncing && (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
              <RefreshCw className="w-5 h-5 text-blue-500 animate-spin flex-shrink-0" />
              <span className="text-sm text-blue-700 dark:text-blue-300">正在同步，请稍候…</span>
            </div>
          )}

          {result && (
            <div className="space-y-2">
              {result.accepted ? (
                <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                  <CheckCircle className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-blue-700 dark:text-blue-300">
                    <span className="font-medium">同步任务已提交</span>
                    <span className="block text-xs mt-0.5">预计 1-10 分钟完成，您可以关闭此对话框继续其他操作。</span>
                  </div>
                </div>
              ) : (
                <>
                  {result.categories && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                      <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <div className="text-sm text-green-700 dark:text-green-300">
                        <span className="font-medium">分类同步完成</span>
                        <span className="block text-xs mt-0.5">
                          新增 {result.categories.inserted} · 更新 {result.categories.updated} · 共 {result.categories.total_seen} 条
                        </span>
                      </div>
                    </div>
                  )}
                  {result.goods && (
                    <div className="flex items-start gap-3 p-3 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                      <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <div className="text-sm text-green-700 dark:text-green-300">
                        <span className="font-medium">商品同步完成</span>
                        <span className="block text-xs mt-0.5">
                          新增 {result.goods.inserted} · 更新 {result.goods.updated} · 共 {result.goods.total_seen} 条
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn-ios-secondary" disabled={syncing}>
            {result ? '关闭' : '取消'}
          </button>
          {!result && (
            <button
              type="button"
              onClick={handleSync}
              className="btn-ios-primary"
              disabled={syncing || (!syncCategories && !syncGoods)}
            >
              {syncing ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  同步中…
                </span>
              ) : (
                '开始同步'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
