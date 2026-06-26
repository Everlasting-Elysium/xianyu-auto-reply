import { useState } from 'react'
import { X, Loader2, RotateCw, XCircle } from 'lucide-react'
import { retryChargeOrder, cancelChargeOrder, type ChargeOrder, type ChargeOrderStatus } from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'

const statusLabels: Record<ChargeOrderStatus, string> = {
  pending: '待处理',
  collecting: '收集信息中',
  ready: '待下单',
  ordering: '下单中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

const statusBadge: Record<ChargeOrderStatus, string> = {
  pending: 'badge-gray',
  collecting: 'badge-info',
  ready: 'badge-warning',
  ordering: 'badge-info',
  success: 'badge-success',
  failed: 'badge-danger',
  cancelled: 'badge-gray',
}

interface Props {
  order: ChargeOrder
  onClose: () => void
  onRefresh: () => void
}

export function ChargeOrderDetailModal({ order, onClose, onRefresh }: Props) {
  const { addToast } = useUIStore()
  const [retrying, setRetrying] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [resetRetryCount, setResetRetryCount] = useState(false)

  const canRetry = order.status === 'failed' || order.status === 'ready'
  const canCancel = !['success', 'cancelled'].includes(order.status)

  const handleRetry = async () => {
    setRetrying(true)
    try {
      await retryChargeOrder(order.id, resetRetryCount)
      addToast({ type: 'success', message: '重试已发起' })
      onRefresh()
      onClose()
    } catch {
      addToast({ type: 'error', message: '重试失败' })
    } finally {
      setRetrying(false)
    }
  }

  const handleCancel = async () => {
    setCancelling(true)
    try {
      await cancelChargeOrder(order.id)
      addToast({ type: 'success', message: '订单已取消' })
      onRefresh()
      onClose()
    } catch {
      addToast({ type: 'error', message: '取消失败' })
    } finally {
      setCancelling(false)
    }
  }

  const fmt = (dt: string | null) => dt ? new Date(dt).toLocaleString('zh-CN') : '-'

  const rows: Array<{ label: string; value: React.ReactNode }> = [
    { label: '订单ID', value: order.id },
    { label: '闲鱼订单号', value: <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">{order.xy_order_no}</code> },
    { label: '闲鱼账号ID', value: order.xy_account_id },
    { label: '买家ID', value: order.buyer_id },
    { label: '买家手机号', value: order.buyer_phone || '-' },
    { label: '平台套餐ID', value: order.platform_sku_id },
    { label: '平台订单号', value: order.platform_order_id || '-' },
    {
      label: '状态',
      value: <span className={`${statusBadge[order.status]} text-xs`}>{statusLabels[order.status]}</span>,
    },
    { label: '重试次数', value: `${order.retry_count} / ${order.max_retries}` },
    { label: '下次重试时间', value: fmt(order.next_retry_at) },
    { label: '创建时间', value: fmt(order.created_at) },
    { label: '更新时间', value: fmt(order.updated_at) },
  ]

  return (
    <div className="modal-overlay" style={{ zIndex: 60 }}>
      <div className="modal-content max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="modal-header flex items-center justify-between sticky top-0 bg-white dark:bg-gray-900 z-10">
          <h2 className="text-lg font-semibold">订单详情</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        <div className="modal-body space-y-4">
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {rows.map(row => (
              <div key={row.label} className="flex items-center justify-between py-2.5">
                <span className="text-sm text-gray-500 dark:text-gray-400">{row.label}</span>
                <span className="text-sm font-medium text-gray-900 dark:text-white">{row.value}</span>
              </div>
            ))}
          </div>

          {order.fail_reason && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
              <p className="text-sm font-medium text-red-700 dark:text-red-400 mb-1">失败原因</p>
              <p className="text-sm text-red-600 dark:text-red-300 break-words">{order.fail_reason}</p>
            </div>
          )}

          {canRetry && (
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="resetRetryCount"
                checked={resetRetryCount}
                onChange={e => setResetRetryCount(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="resetRetryCount" className="text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                重置重试计数
              </label>
            </div>
          )}
        </div>

        <div className="modal-footer sticky bottom-0 bg-white dark:bg-gray-900">
          <button type="button" onClick={onClose} className="btn-ios-secondary">关闭</button>
          <div className="flex gap-2">
            {canCancel && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling}
                className="btn-ios-danger"
              >
                {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                取消订单
              </button>
            )}
            {canRetry && (
              <button
                type="button"
                onClick={handleRetry}
                disabled={retrying}
                className="btn-ios-primary"
              >
                {retrying ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCw className="w-4 h-4" />}
                重试
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
