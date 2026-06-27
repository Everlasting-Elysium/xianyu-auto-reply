import { useState, useEffect } from 'react'
import type { FormEvent } from 'react'
import { X, Loader2 } from 'lucide-react'
import {
  createChargeSkuMapping,
  updateChargeSkuMapping,
  getChargePlatformConfigs,
  type ChargeSkuMapping,
  type ChargePlatformConfig,
} from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'
import { getApiErrorMessage } from '@/utils/request'

interface MappingFormData {
  platform_config_id: string
  item_id: string
  spec_value: string
  platform_sku_id: string
  platform_sku_name: string
  is_active: boolean
  remark: string
}

const emptyForm: MappingFormData = {
  platform_config_id: '',
  item_id: '',
  spec_value: '',
  platform_sku_id: '',
  platform_sku_name: '',
  is_active: true,
  remark: '',
}

function mappingToForm(mapping: ChargeSkuMapping): MappingFormData {
  return {
    platform_config_id: String(mapping.platform_config_id),
    item_id: mapping.item_id,
    spec_value: mapping.spec_value || '',
    platform_sku_id: mapping.platform_sku_id,
    platform_sku_name: mapping.platform_sku_name || '',
    is_active: mapping.is_active,
    remark: mapping.remark || '',
  }
}

interface Props {
  mapping: ChargeSkuMapping | null
  onClose: () => void
  onSaved: () => void
}

export function ChargeSkuMappingFormModal({ mapping, onClose, onSaved }: Props) {
  const { addToast } = useUIStore()
  const [form, setForm] = useState<MappingFormData>(mapping ? mappingToForm(mapping) : emptyForm)
  const [saving, setSaving] = useState(false)
  const [configs, setConfigs] = useState<ChargePlatformConfig[]>([])
  const isEdit = mapping !== null

  useEffect(() => {
    getChargePlatformConfigs({ page_size: 100 })
      .then(res => setConfigs(res.items || []))
      .catch((error) => addToast({ type: 'error', message: getApiErrorMessage(error, '加载平台账号列表失败') }))
  }, [])

  const updateField = <K extends keyof MappingFormData>(field: K, value: MappingFormData[K]) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const validate = (): boolean => {
    if (!form.platform_config_id) { addToast({ type: 'warning', message: '请选择平台账号' }); return false }
    if (!form.item_id.trim()) { addToast({ type: 'warning', message: '请输入闲鱼商品ID' }); return false }
    if (!form.platform_sku_id.trim()) { addToast({ type: 'warning', message: '请输入平台套餐ID' }); return false }
    return true
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        platform_config_id: Number(form.platform_config_id),
        item_id: form.item_id.trim(),
        spec_value: form.spec_value.trim() || null,
        platform_sku_id: form.platform_sku_id.trim(),
        platform_sku_name: form.platform_sku_name.trim() || null,
        is_active: form.is_active,
        remark: form.remark.trim(),
      }
      if (isEdit) {
        await updateChargeSkuMapping(mapping!.id, payload)
        addToast({ type: 'success', message: '映射已更新' })
      } else {
        await createChargeSkuMapping(payload)
        addToast({ type: 'success', message: '映射已创建' })
      }
      onSaved()
      onClose()
    } catch (error) {
      addToast({ type: 'error', message: getApiErrorMessage(error, isEdit ? '更新失败' : '创建失败') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 60 }}>
      <div className="modal-content max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="modal-header flex items-center justify-between sticky top-0 bg-white dark:bg-gray-900 z-10">
          <h2 className="text-lg font-semibold">{isEdit ? '编辑套餐映射' : '新建套餐映射'}</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body space-y-4">
            <div>
              <label className="input-label">平台账号 <span className="text-red-500">*</span></label>
              <select
                value={form.platform_config_id}
                onChange={e => updateField('platform_config_id', e.target.value)}
                className="input-ios"
              >
                <option value="">请选择平台账号</option>
                {configs.map(c => (
                  <option key={c.id} value={String(c.id)}>{c.name}（{c.username}）</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                {/* TODO: 后续可改为从商品列表下拉选择 */}
                <label className="input-label">闲鱼商品ID <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.item_id}
                  onChange={e => updateField('item_id', e.target.value)}
                  className="input-ios"
                  placeholder="闲鱼商品ID"
                />
              </div>
              <div>
                <label className="input-label">规格值</label>
                <input
                  type="text"
                  value={form.spec_value}
                  onChange={e => updateField('spec_value', e.target.value)}
                  className="input-ios"
                  placeholder="留空表示匹配所有规格"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="input-label">平台套餐ID <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  value={form.platform_sku_id}
                  onChange={e => updateField('platform_sku_id', e.target.value)}
                  className="input-ios"
                  placeholder="充值平台的套餐ID"
                />
              </div>
              <div>
                <label className="input-label">平台套餐名称</label>
                <input
                  type="text"
                  value={form.platform_sku_name}
                  onChange={e => updateField('platform_sku_name', e.target.value)}
                  className="input-ios"
                  placeholder="仅展示用，如 30元话费"
                />
              </div>
            </div>

            <div>
              <label className="input-label">备注</label>
              <textarea
                value={form.remark}
                onChange={e => updateField('remark', e.target.value)}
                className="input-ios h-20"
                placeholder="可选备注"
              />
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="mappingActive"
                checked={form.is_active}
                onChange={e => updateField('is_active', e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <label htmlFor="mappingActive" className="text-sm font-medium text-gray-900 dark:text-white cursor-pointer">
                启用此映射
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
