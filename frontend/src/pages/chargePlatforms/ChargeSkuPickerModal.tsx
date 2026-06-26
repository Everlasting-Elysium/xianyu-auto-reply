import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  X, Search, ChevronRight, ChevronDown, ChevronLeft,
  ArrowUpDown, ArrowUp, ArrowDown, RefreshCw, Check, Package,
} from 'lucide-react'
import {
  listCategories, listGoods,
  type ChargePlatformCategory, type ChargePlatformGoods, type GoodsOrderBy,
} from '@/api/chargePlatforms'
import { useUIStore } from '@/store/uiStore'

interface CategoryNode extends ChargePlatformCategory {
  children: CategoryNode[]
}

function buildCategoryTree(flat: ChargePlatformCategory[]): CategoryNode[] {
  const map = new Map<number, CategoryNode>()
  const roots: CategoryNode[] = []

  for (const c of flat) {
    map.set(c.id, { ...c, children: [] })
  }
  for (const node of map.values()) {
    if (node.parent_id && map.has(node.parent_id)) {
      map.get(node.parent_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
}

function CategoryTreeItem({
  node, depth, selectedName, onSelect,
}: {
  node: CategoryNode
  depth: number
  selectedName: string | null
  onSelect: (name: string) => void
}) {
  const [expanded, setExpanded] = useState(depth === 0)
  const hasChildren = node.children.length > 0
  const isSelected = selectedName === node.name

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          onSelect(node.name)
          if (hasChildren) setExpanded(prev => !prev)
        }}
        className={`w-full flex items-center gap-1 px-2 py-1.5 text-sm rounded-md transition-colors ${
          isSelected
            ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium'
            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          expanded
            ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" />
            : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" />
        ) : (
          <span className="w-3.5" />
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {expanded && hasChildren && (
        <div>
          {node.children.map(child => (
            <CategoryTreeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedName={selectedName}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface Props {
  platformConfigId: number
  selectedIds: number[]
  onConfirm: (ids: number[]) => void
  onClose: () => void
}

export function ChargeSkuPickerModal({ platformConfigId, selectedIds, onConfirm, onClose }: Props) {
  const { addToast } = useUIStore()

  const [categories, setCategories] = useState<ChargePlatformCategory[]>([])
  const [catLoading, setCatLoading] = useState(true)
  const [selectedCatName, setSelectedCatName] = useState<string | null>(null)

  const [goods, setGoods] = useState<ChargePlatformGoods[]>([])
  const [goodsLoading, setGoodsLoading] = useState(false)
  const [goodsTotal, setGoodsTotal] = useState(0)
  const [goodsPage, setGoodsPage] = useState(1)
  const [goodsPageSize] = useState(20)

  const [keyword, setKeyword] = useState('')
  const [orderBy, setOrderBy] = useState<GoodsOrderBy | ''>('')

  const [picked, setPicked] = useState<Set<number>>(new Set(selectedIds))

  const categoryTree = useMemo(() => buildCategoryTree(categories), [categories])

  const uniqueClass1 = useMemo(() => {
    const s = new Set<string>()
    categories.forEach(c => { if (c.name) s.add(c.name) })
    return Array.from(s).sort()
  }, [categories])

  useEffect(() => {
    setCatLoading(true)
    listCategories(platformConfigId)
      .then(setCategories)
      .catch(() => addToast({ type: 'error', message: '加载分类失败' }))
      .finally(() => setCatLoading(false))
  }, [platformConfigId, addToast])

  const loadGoods = useCallback(async (p?: number) => {
    const page = p ?? goodsPage
    setGoodsLoading(true)
    try {
      const res = await listGoods({
        platformConfigId,
        page,
        pageSize: goodsPageSize,
        keyword: keyword || undefined,
        className1: selectedCatName || undefined,
        onlyActive: true,
        orderBy: orderBy || undefined,
      })
      setGoods(res.items || [])
      setGoodsTotal(res.total || 0)
    } catch {
      addToast({ type: 'error', message: '加载商品列表失败' })
    } finally {
      setGoodsLoading(false)
    }
  }, [platformConfigId, goodsPage, goodsPageSize, keyword, selectedCatName, orderBy, addToast])

  useEffect(() => {
    setGoodsPage(1)
    loadGoods(1)
  }, [selectedCatName, orderBy])

  useEffect(() => {
    const t = setTimeout(() => {
      setGoodsPage(1)
      loadGoods(1)
    }, 350)
    return () => clearTimeout(t)
  }, [keyword])

  const totalPages = Math.ceil(goodsTotal / goodsPageSize) || 1

  const togglePick = (id: number) => {
    setPicked(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleConfirm = () => {
    onConfirm(Array.from(picked))
    onClose()
  }

  const cycleOrder = () => {
    const cycle: (GoodsOrderBy | '')[] = ['', 'price_asc', 'price_desc']
    const idx = cycle.indexOf(orderBy)
    setOrderBy(cycle[(idx + 1) % cycle.length])
  }

  const OrderIcon = orderBy === 'price_asc' ? ArrowUp : orderBy === 'price_desc' ? ArrowDown : ArrowUpDown

  return (
    <div className="modal-overlay" style={{ zIndex: 80 }}>
      <div className="modal-content max-w-5xl" style={{ height: 'min(85vh, 720px)' }}>
        <div className="modal-header flex items-center justify-between sticky top-0 bg-white dark:bg-gray-900 z-10">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-500" />
            选择 SKU 商品
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              已选 <span className="font-medium text-blue-600 dark:text-blue-400">{picked.size}</span> 项
            </span>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden" style={{ height: 'calc(100% - 130px)' }}>
          {/* Left: Category tree */}
          <div className="w-52 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 overflow-y-auto p-2">
            <div className="mb-2">
              <button
                type="button"
                onClick={() => setSelectedCatName(null)}
                className={`w-full text-left px-2 py-1.5 text-sm rounded-md transition-colors ${
                  selectedCatName === null
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                全部分类
              </button>
            </div>
            {catLoading ? (
              <div className="flex justify-center py-6">
                <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
              </div>
            ) : categoryTree.length > 0 ? (
              categoryTree.map(node => (
                <CategoryTreeItem
                  key={node.id}
                  node={node}
                  depth={0}
                  selectedName={selectedCatName}
                  onSelect={setSelectedCatName}
                />
              ))
            ) : uniqueClass1.length > 0 ? (
              uniqueClass1.map(name => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setSelectedCatName(name)}
                  className={`w-full text-left px-2 py-1.5 text-sm rounded-md transition-colors ${
                    selectedCatName === name
                      ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  {name}
                </button>
              ))
            ) : (
              <p className="text-xs text-gray-400 text-center mt-4">暂无分类</p>
            )}
          </div>

          {/* Right: search + goods list */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Toolbar */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
              <div className="relative flex-1 max-w-xs">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={keyword}
                  onChange={e => setKeyword(e.target.value)}
                  placeholder="搜索商品名称…"
                  className="input-ios pl-9 py-1.5 text-sm"
                />
              </div>
              <button
                type="button"
                onClick={cycleOrder}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  orderBy
                    ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                    : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
                title="切换价格排序"
              >
                <OrderIcon className="w-3.5 h-3.5" />
                价格{orderBy === 'price_asc' ? '↑' : orderBy === 'price_desc' ? '↓' : ''}
              </button>
            </div>

            {/* Goods list */}
            <div className="flex-1 overflow-y-auto">
              {goodsLoading ? (
                <div className="flex justify-center py-12">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : goods.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                  <Package className="w-10 h-10 mb-2 opacity-40" />
                  <p className="text-sm">暂无商品</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-800">
                  {goods.map(g => {
                    const isPicked = picked.has(g.id)
                    return (
                      <label
                        key={g.id}
                        className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                          isPicked
                            ? 'bg-blue-50/60 dark:bg-blue-900/15'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                          isPicked
                            ? 'bg-blue-500 border-blue-500'
                            : 'border-gray-300 dark:border-gray-600'
                        }`}>
                          {isPicked && <Check className="w-3.5 h-3.5 text-white" />}
                        </div>
                        <input
                          type="checkbox"
                          className="hidden"
                          checked={isPicked}
                          onChange={() => togglePick(g.id)}
                        />

                        {g.thumb && (
                          <img
                            src={g.thumb}
                            alt=""
                            className="w-10 h-10 rounded-md object-cover flex-shrink-0 border border-gray-200 dark:border-gray-700"
                          />
                        )}

                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                            {g.name}
                          </p>
                          <div className="flex items-center gap-3 mt-0.5">
                            {g.class_name_1 && (
                              <span className="text-[11px] text-gray-500 dark:text-gray-400">{g.class_name_1}</span>
                            )}
                            {g.class_name_2 && (
                              <span className="text-[11px] text-gray-500 dark:text-gray-400">/ {g.class_name_2}</span>
                            )}
                            <span className="text-[11px] text-gray-400">ID:{g.id}</span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end flex-shrink-0">
                          <span className="text-sm font-semibold text-amber-600 dark:text-amber-400">¥{g.price}</span>
                          <span className="text-[11px] text-gray-400">
                            库存 {g.stock} · {g.min_order_num}-{g.max_order_num}
                          </span>
                        </div>
                      </label>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Pagination */}
            {goodsTotal > 0 && (
              <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 dark:border-gray-700 flex-shrink-0 text-sm text-gray-500">
                <span>共 {goodsTotal} 个商品</span>
                <div className="flex items-center gap-2">
                  <span>第 {goodsPage}/{totalPages} 页</span>
                  <button
                    onClick={() => { const p = Math.max(1, goodsPage - 1); setGoodsPage(p); loadGoods(p) }}
                    disabled={goodsPage <= 1}
                    className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => { const p = Math.min(totalPages, goodsPage + 1); setGoodsPage(p); loadGoods(p) }}
                    disabled={goodsPage >= totalPages}
                    className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Selected bar + actions */}
        {picked.size > 0 && (
          <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
            <div className="flex flex-wrap gap-1.5 max-h-16 overflow-y-auto">
              {Array.from(picked).map(id => {
                const g = goods.find(x => x.id === id)
                return (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                  >
                    {g ? g.name.slice(0, 16) : `#${id}`}
                    <button
                      type="button"
                      onClick={() => togglePick(id)}
                      className="hover:text-red-500 transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )
              })}
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn-ios-secondary">取消</button>
          <button type="button" onClick={handleConfirm} className="btn-ios-primary">
            确认选择 ({picked.size})
          </button>
        </div>
      </div>
    </div>
  )
}
