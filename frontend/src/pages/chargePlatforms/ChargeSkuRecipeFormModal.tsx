import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  X, Loader2, Plus, Trash2, Package, ChevronUp, ChevronDown,
  BookOpen, RefreshCw,
} from 'lucide-react'
import {
  getRecipe, createRecipe, updateRecipe,
  getChargePlatformConfigs, listCategories,
  type ChargePlatformConfig, type ChargePlatformCategory,
} from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'
import { ChargeSkuPickerModal } from './ChargeSkuPickerModal'

interface RecipeItemForm {
  _key: string
  tag: string
  preferred_sku_ids: number[]
  fallback_class_name_1: string
  fallback_class_name_2: string
  quantity: number
  cf_count: number
  overrides_json: string
  is_active: boolean
}

interface Props {
  recipeId: number | null
  onClose: () => void
  onSaved: () => void
}

let _keySeq = 0
const nextKey = () => `ri_${Date.now()}_${++_keySeq}`

const emptyItem = (): RecipeItemForm => ({
  _key: nextKey(),
  tag: '',
  preferred_sku_ids: [],
  fallback_class_name_1: '',
  fallback_class_name_2: '',
  quantity: 1,
  cf_count: 1,
  overrides_json: '',
  is_active: true,
})

export function ChargeSkuRecipeFormModal({ recipeId, onClose, onSaved }: Props) {
  const { addToast } = useUIStore()
  const isEdit = recipeId !== null

  // ── Form fields ──
  const [name, setName] = useState('')
  const [itemId, setItemId] = useState('')
  const [specValue, setSpecValue] = useState('')
  const [platformConfigId, setPlatformConfigId] = useState<number | ''>('')
  const [description, setDescription] = useState('')
  const [requireInputKeys, setRequireInputKeys] = useState<string[]>([])
  const [newKeyInput, setNewKeyInput] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [items, setItems] = useState<RecipeItemForm[]>([emptyItem()])

  // ── Reference data ──
  const [configs, setConfigs] = useState<ChargePlatformConfig[]>([])
  const [categories, setCategories] = useState<ChargePlatformCategory[]>([])

  // ── UI state ──
  const [initLoading, setInitLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [skuPickerIdx, setSkuPickerIdx] = useState<number | null>(null)

  // ── Load platform configs ──
  useEffect(() => {
    getChargePlatformConfigs({ page: 1, page_size: 200 })
      .then(r => setConfigs(r.items || []))
      .catch(() => addToast({ type: 'error', message: '加载平台账号失败' }))
  }, [addToast])

  // ── Load categories when platform changes ──
  useEffect(() => {
    if (!platformConfigId) { setCategories([]); return }
    listCategories(platformConfigId as number)
      .then(setCategories)
      .catch(() => {/* silent – categories are optional */})
  }, [platformConfigId])

  // ── Load recipe for editing ──
  useEffect(() => {
    if (recipeId === null) return
    setInitLoading(true)
    getRecipe(recipeId)
      .then(r => {
        setName(r.name)
        setItemId(r.item_id)
        setSpecValue(r.spec_value || '')
        setPlatformConfigId(r.platform_config_id)
        setDescription(r.description || '')
        setRequireInputKeys(r.require_input_keys || [])
        setIsActive(r.is_active)
        setItems(
          (r.items || []).length > 0
            ? r.items.map(it => ({
                _key: nextKey(),
                tag: it.tag,
                preferred_sku_ids: it.preferred_sku_ids || [],
                fallback_class_name_1: it.fallback_class_name_1 || '',
                fallback_class_name_2: it.fallback_class_name_2 || '',
                quantity: it.quantity,
                cf_count: it.cf_count,
                overrides_json: it.input_value_overrides
                  ? JSON.stringify(it.input_value_overrides, null, 2)
                  : '',
                is_active: it.is_active,
              }))
            : [emptyItem()],
        )
      })
      .catch(() => { addToast({ type: 'error', message: '加载配方详情失败' }); onClose() })
      .finally(() => setInitLoading(false))
  }, [recipeId, addToast, onClose])

  // ── Category helpers ──
  const rootCats = useMemo(() => categories.filter(c => !c.parent_id), [categories])

  const childCatsOf = useCallback((parentName: string) => {
    const parent = categories.find(c => !c.parent_id && c.name === parentName)
    if (!parent) return []
    return categories.filter(c => c.parent_id === parent.id)
  }, [categories])

  // ── Item CRUD ──
  const updateItem = (i: number, patch: Partial<RecipeItemForm>) =>
    setItems(prev => prev.map((it, idx) => idx === i ? { ...it, ...patch } : it))

  const removeItem = (i: number) => {
    if (items.length <= 1) { addToast({ type: 'warning', message: '至少保留一个子项' }); return }
    setItems(prev => prev.filter((_, idx) => idx !== i))
  }

  const moveItem = (i: number, dir: 'up' | 'down') => {
    setItems(prev => {
      const arr = [...prev]
      const j = dir === 'up' ? i - 1 : i + 1
      if (j < 0 || j >= arr.length) return prev
      ;[arr[i], arr[j]] = [arr[j], arr[i]]
      return arr
    })
  }

  // ── Tag input helpers ──
  const addKey = () => {
    const k = newKeyInput.trim()
    if (!k) return
    if (requireInputKeys.includes(k)) { addToast({ type: 'warning', message: '该参数已存在' }); return }
    setRequireInputKeys(prev => [...prev, k])
    setNewKeyInput('')
  }

  // ── Validation ──
  const validate = (): boolean => {
    if (!name.trim()) { addToast({ type: 'warning', message: '请输入配方名称' }); return false }
    if (!itemId.trim()) { addToast({ type: 'warning', message: '请输入闲鱼商品ID' }); return false }
    if (!platformConfigId) { addToast({ type: 'warning', message: '请选择平台账号' }); return false }
    if (items.length === 0) { addToast({ type: 'warning', message: '至少添加一个子项' }); return false }
    for (let idx = 0; idx < items.length; idx++) {
      const it = items[idx]
      if (!it.tag.trim()) { addToast({ type: 'warning', message: `子项 #${idx + 1} 的标签不能为空` }); return false }
      if (it.quantity < 1) { addToast({ type: 'warning', message: `子项 #${idx + 1} 的数量至少为 1` }); return false }
      if (it.preferred_sku_ids.length === 0 && !it.fallback_class_name_1) {
        addToast({ type: 'warning', message: `子项 #${idx + 1} 需要设置优先 SKU 或兜底分类` }); return false
      }
      if (it.overrides_json.trim()) {
        try { JSON.parse(it.overrides_json) } catch {
          addToast({ type: 'warning', message: `子项 #${idx + 1} 的参数覆盖 JSON 格式不正确` }); return false
        }
      }
    }
    return true
  }

  // ── Submit ──
  const handleSubmit = async () => {
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        platform_config_id: platformConfigId as number,
        item_id: itemId.trim(),
        spec_value: specValue.trim() || null,
        name: name.trim(),
        description: description.trim(),
        require_input_keys: requireInputKeys,
        is_active: isActive,
        items: items.map((it, idx) => ({
          sort: idx,
          tag: it.tag.trim(),
          preferred_sku_ids: it.preferred_sku_ids.length > 0 ? it.preferred_sku_ids : null,
          fallback_class_name_1: it.fallback_class_name_1 || null,
          fallback_class_name_2: it.fallback_class_name_2 || null,
          quantity: it.quantity,
          cf_count: it.cf_count,
          input_value_overrides: it.overrides_json.trim()
            ? JSON.parse(it.overrides_json) as Record<string, string>
            : null,
          is_active: it.is_active,
        })),
      }
      if (recipeId !== null) {
        await updateRecipe(recipeId, payload)
        addToast({ type: 'success', message: '配方已更新' })
      } else {
        await createRecipe(payload)
        addToast({ type: 'success', message: '配方已创建' })
      }
      onSaved()
      onClose()
    } catch {
      addToast({ type: 'error', message: isEdit ? '更新配方失败' : '创建配方失败' })
    } finally {
      setSaving(false)
    }
  }

  // ── Render ──
  return (
    <>
      <div className="modal-overlay" style={{ zIndex: 60 }}>
        <div className="modal-content max-w-3xl max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="modal-header flex items-center justify-between sticky top-0 bg-white dark:bg-gray-900 z-10">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-blue-500" />
              {isEdit ? '编辑配方' : '新建配方'}
            </h2>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>

          {/* Body */}
          <div className="modal-body space-y-4">
            {initLoading ? (
              <div className="flex justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            ) : (
              <>
                {/* Row 1: name / item_id / spec */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="input-label">配方名称 <span className="text-red-500">*</span></label>
                    <input type="text" value={name} onChange={e => setName(e.target.value)} className="input-ios" placeholder="如：月卡30天" />
                  </div>
                  <div>
                    <label className="input-label">闲鱼商品ID <span className="text-red-500">*</span></label>
                    <input type="text" value={itemId} onChange={e => setItemId(e.target.value)} className="input-ios" placeholder="商品ID" />
                  </div>
                  <div>
                    <label className="input-label">规格值</label>
                    <input type="text" value={specValue} onChange={e => setSpecValue(e.target.value)} className="input-ios" placeholder="可选，精确匹配" />
                  </div>
                </div>

                {/* Platform config */}
                <div>
                  <label className="input-label">平台账号 <span className="text-red-500">*</span></label>
                  <select
                    value={platformConfigId}
                    onChange={e => setPlatformConfigId(e.target.value ? Number(e.target.value) : '')}
                    className="input-ios"
                  >
                    <option value="">请选择平台账号</option>
                    {configs.map(c => (
                      <option key={c.id} value={c.id}>{c.name} ({c.username})</option>
                    ))}
                  </select>
                </div>

                {/* Description */}
                <div>
                  <label className="input-label">描述</label>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    className="input-ios h-20"
                    placeholder="配方用途说明（可选）"
                  />
                </div>

                {/* Require input keys – tag input */}
                <div>
                  <label className="input-label">必填参数 Keys</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={newKeyInput}
                      onChange={e => setNewKeyInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addKey() } }}
                      className="input-ios flex-1"
                      placeholder="输入参数名后按 Enter 添加"
                    />
                    <button type="button" onClick={addKey} className="btn-ios-secondary btn-sm whitespace-nowrap">添加</button>
                  </div>
                  {requireInputKeys.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {requireInputKeys.map(k => (
                        <span
                          key={k}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                        >
                          {k}
                          <button
                            type="button"
                            onClick={() => setRequireInputKeys(prev => prev.filter(x => x !== k))}
                            className="hover:text-red-500 transition-colors"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Is active */}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={e => setIsActive(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <span className="text-sm font-medium text-gray-900 dark:text-white">启用配方</span>
                </label>

                {/* ── Sub-items ── */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium text-gray-900 dark:text-white">子项列表</h3>
                    <button type="button" onClick={() => setItems(prev => [...prev, emptyItem()])} className="btn-ios-secondary btn-sm">
                      <Plus className="w-3.5 h-3.5" />
                      添加子项
                    </button>
                  </div>

                  {items.map((item, idx) => (
                    <div key={item._key} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
                      {/* Item header */}
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">子项 #{idx + 1}</span>
                        <div className="flex items-center gap-1">
                          <button type="button" onClick={() => moveItem(idx, 'up')} disabled={idx === 0}
                            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title="上移">
                            <ChevronUp className="w-4 h-4" />
                          </button>
                          <button type="button" onClick={() => moveItem(idx, 'down')} disabled={idx === items.length - 1}
                            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30" title="下移">
                            <ChevronDown className="w-4 h-4" />
                          </button>
                          <button type="button" onClick={() => removeItem(idx)}
                            className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500" title="删除子项">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* tag / quantity / cf_count */}
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className="input-label">标签 <span className="text-red-500">*</span></label>
                          <input type="text" value={item.tag} onChange={e => updateItem(idx, { tag: e.target.value })}
                            className="input-ios" placeholder="如：主商品" />
                        </div>
                        <div>
                          <label className="input-label">数量 <span className="text-red-500">*</span></label>
                          <input type="number" value={item.quantity} min={1}
                            onChange={e => updateItem(idx, { quantity: Math.max(1, parseInt(e.target.value) || 1) })}
                            className="input-ios" />
                        </div>
                        <div>
                          <label className="input-label">重复次数</label>
                          <input type="number" value={item.cf_count} min={1}
                            onChange={e => updateItem(idx, { cf_count: Math.max(1, parseInt(e.target.value) || 1) })}
                            className="input-ios" />
                        </div>
                      </div>

                      {/* Selection strategy */}
                      <div className="space-y-2">
                        <label className="input-label">选品策略</label>

                        {/* Preferred SKU */}
                        <div className="flex items-center gap-3">
                          <span className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">优先 SKU:</span>
                          <button
                            type="button"
                            onClick={() => {
                              if (!platformConfigId) { addToast({ type: 'warning', message: '请先选择平台账号' }); return }
                              setSkuPickerIdx(idx)
                            }}
                            className="btn-ios-secondary btn-sm"
                          >
                            <Package className="w-3.5 h-3.5" />
                            选择 SKU
                          </button>
                          {item.preferred_sku_ids.length > 0 && (
                            <span className="badge-info text-xs">已选 {item.preferred_sku_ids.length} 个</span>
                          )}
                        </div>

                        {/* Fallback category */}
                        <div className="flex items-center gap-3">
                          <span className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">兜底分类:</span>
                          <select
                            value={item.fallback_class_name_1}
                            onChange={e => updateItem(idx, { fallback_class_name_1: e.target.value, fallback_class_name_2: '' })}
                            className="input-ios text-sm flex-1"
                          >
                            <option value="">一级分类</option>
                            {rootCats.map(c => (
                              <option key={c.id} value={c.name}>{c.name}</option>
                            ))}
                          </select>
                          <select
                            value={item.fallback_class_name_2}
                            onChange={e => updateItem(idx, { fallback_class_name_2: e.target.value })}
                            className="input-ios text-sm flex-1"
                            disabled={!item.fallback_class_name_1}
                          >
                            <option value="">二级分类</option>
                            {item.fallback_class_name_1 && childCatsOf(item.fallback_class_name_1).map(c => (
                              <option key={c.id} value={c.name}>{c.name}</option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Overrides */}
                      <div>
                        <label className="input-label">参数覆盖 (JSON)</label>
                        <textarea
                          value={item.overrides_json}
                          onChange={e => updateItem(idx, { overrides_json: e.target.value })}
                          className="input-ios h-16 font-mono text-sm"
                          placeholder='{"key": "value"}'
                        />
                      </div>

                      {/* Item active */}
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={item.is_active}
                          onChange={e => updateItem(idx, { is_active: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-300" />
                        <span className="text-sm text-gray-700 dark:text-gray-300">启用</span>
                      </label>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Footer */}
          <div className="modal-footer sticky bottom-0 bg-white dark:bg-gray-900">
            <button type="button" onClick={onClose} className="btn-ios-secondary" disabled={saving}>取消</button>
            <button type="button" onClick={handleSubmit} className="btn-ios-primary" disabled={saving || initLoading}>
              {saving
                ? <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />保存中…</span>
                : '保存'
              }
            </button>
          </div>
        </div>
      </div>

      {/* SKU Picker – rendered outside the modal to avoid z-index/overflow issues */}
      {skuPickerIdx !== null && typeof platformConfigId === 'number' && (
        <ChargeSkuPickerModal
          platformConfigId={platformConfigId}
          selectedIds={items[skuPickerIdx]?.preferred_sku_ids || []}
          onConfirm={ids => updateItem(skuPickerIdx, { preferred_sku_ids: ids })}
          onClose={() => setSkuPickerIdx(null)}
        />
      )}
    </>
  )
}
