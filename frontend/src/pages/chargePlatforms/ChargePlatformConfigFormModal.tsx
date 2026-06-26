import { useState } from 'react'
import type { FormEvent } from 'react'
import { X, Loader2 } from 'lucide-react'
import {
  createChargePlatformConfig,
  updateChargePlatformConfig,
  type ChargePlatformConfig,
} from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'

interface ConfigFormData {
  name: string
  platform_url: string
  username: string
  password: string
  balance_alert_threshold: string
  max_orders_per_hour: string
  enabled: boolean
  remark: string
}

const emptyForm: ConfigFormData = {
  name: '',
  platform_url: 'https://xckj9.008e1.top',
  username: '',
  password: '',
  balance_alert_threshold: '50',
  max_orders_per_hour: '20',
  enabled: true,
  remark: '',
}

function configToForm(config: ChargePlatformConfig): ConfigFormData {
  return {
    name: config.name,
    platform_url: config.platform_url,
    username: config.username,
    password: '',
    balance_alert_threshold: config.balance_alert_threshold || '50',
    max_orders_per_hour: String(config.max_orders_per_hour),
    enabled: config.enabled,
    remark: config.remark || '',
  }
}

interface Props {
  config: ChargePlatformConfig | null
  onClose: () => void
  onSaved: () => void
}

export function ChargePlatformConfigFormModal({ config, onClose, onSaved }: Props) {
  const { addToast } = useUIStore()
  const [form, setForm] = useState<ConfigFormData>(config ? configToForm(config) : emptyForm)
  const [saving, setSaving] = useState(false)
  const isEdit = config !== null

  const updateField = <K extends keyof ConfigFormData>(field: K, value: ConfigFormData[K]) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const validate = (): boolean => {
    if (!form.name.trim()) { addToast({ type: 'warning', message: '请输入账号别名' }); return false }
    if (!form.username.trim()) { addToast({ type: 'warning', message: '请输入用户名' }); return false }
    if (!isEdit && !form.password.trim()) { addToast({ type: 'warning', message: '请输入密码' }); return false }
    if (!form.platform_url.trim()) { addToast({ type: 'warning', message: '请输入平台地址' }); return false }
    const threshold = Number(form.balance_alert_threshold)
    if (isNaN(threshold) || threshold < 0) { addToast({ type: 'warning', message: '余额告警阈值必须≥0' }); return false }
    const maxOrders = Number(form.max_orders_per_hour)
    if (isNaN(maxOrders) || maxOrders < 1) { addToast({ type: 'warning', message: '每小时最大下单数必须≥1' }); return false }
    return true
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      if (isEdit) {
        const payload: Record<string, unknown> = {
          name: form.name.trim(),
          platform_url: form.platform_url.trim(),
          username: form.username.trim(),
          balance_alert_threshold: Number(form.balance_alert_threshold),
          max_orders_per_hour: Number(form.max_orders_per_hour),
          enabled: form.enabled,
          remark: form.remark.trim(),
        }
        if (form.password.trim()) payload.password = form.password.trim()
        await updateChargePlatformConfig(config!.id, payload)
        addToast({ type: 'success', message: '账号配置已更新' })
      } else {
        await createChargePlatformConfig({
          name: form.name.trim(),
          platform_url: form.platform_url.trim(),
          username: form.username.trim(),
          password: form.password.trim(),
          balance_alert_threshold: Number(form.balance_alert_threshold),
          max_orders_per_hour: Number(form.max_orders_per_hour),
          enabled: form.enabled,
          remark: form.remark.trim(),
        })
        addToast({ type: 'success', message: '账号配置已创建' })
      }
      onSaved()
      onClose()
    } catch {
      addToast({ type: 'error', message: isEdit ? '更新失败' : '创建失败' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 60 }}>
      <div className="modal-content max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="modal-header flex items-center justify-between sticky top-0 bg-white dark:bg-gray-900 z-10">
          <h2 className="text-lg font-semibold">{isEdit ? '编辑平台账号' : '新建平台账号'}</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="input-label">账号别名 <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => updateField('name', e.target.value)}
                  className="input-ios"
                  placeholder="如：主账号、备用账号"
                />
              </div>
              <div>
                <label className="input-label">平台地址 <span className="text-red-500">*</span></label>
                <input
                  type="url"
                  value={form.platform_url}
                  onChange={e => updateField('platform_url', e.target.value)}
                  className="input-ios"
                  placeholder="https://xckj9.008e1.top"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="input-label">用户名 <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.username}
                  onChange={e => updateField('username', e.target.value)}
                  className="input-ios"
                  placeholder="平台登录用户名"
                />
              </div>
              <div>
                <label className="input-label">密码 {!isEdit && <span className="text-red-500">*</span>}</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={e => updateField('password', e.target.value)}
                  className="input-ios"
                  placeholder={isEdit ? '如不修改请留空' : '平台登录密码'}
                />
                {isEdit && (
                  <p className="text-xs text-gray-500 mt-1">如不修改请留空</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="input-label">余额告警阈值</label>
                <input
                  type="number"
                  value={form.balance_alert_threshold}
                  onChange={e => updateField('balance_alert_threshold', e.target.value)}
                  className="input-ios"
                  min={0}
                  step="0.01"
                />
                <p className="text-xs text-gray-500 mt-1">余额低于此值时告警</p>
              </div>
              <div>
                <label className="input-label">每小时最大下单数</label>
                <input
                  type="number"
                  value={form.max_orders_per_hour}
                  onChange={e => updateField('max_orders_per_hour', e.target.value)}
                  className="input-ios"
                  min={1}
                />
              </div>
            </div>

            <div>
              <label className="input-label">备注</label>
              <textarea
                value={form.remark}
                onChange={e => updateField('remark', e.target.value)}
                className="input-ios h-20"
                placeholder="可选备注信息"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="configEnabled"
                checked={form.enabled}
                onChange={e => updateField('enabled', e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="configEnabled" className="text-sm font-medium text-gray-900 dark:text-white cursor-pointer">
                启用此账号
              </label>
            </div>
          </div>

          <div className="modal-footer sticky bottom-0 bg-white dark:bg-gray-900">
            <button type="button" onClick={onClose} className="btn-ios-secondary" disabled={saving}>取消</button>
            <button type="submit" className="btn-ios-primary" disabled={saving}>
              {saving ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  保存中...
                </span>
              ) : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
