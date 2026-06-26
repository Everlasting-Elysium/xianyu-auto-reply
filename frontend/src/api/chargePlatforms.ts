import { get, post, put, del } from '@/utils/request'
import type { ApiResponse } from '@/types'

const PREFIX = '/api/v1/charge-platforms'

export type ChargePlatformStatus = 'active' | 'disabled' | 'risk_controlled' | 'login_failed' | 'balance_low'

export interface ChargePlatformConfig {
  id: number
  name: string
  platform_url: string
  username: string
  password?: string
  balance_alert_threshold: string
  max_orders_per_hour: number
  enabled: boolean
  status: ChargePlatformStatus
  balance: string
  balance_checked_at: string | null
  last_login_at: string | null
  session_expires_at: string | null
  last_error: string | null
  last_error_at: string | null
  remark: string
  extra_config: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface CreateChargePlatformConfig {
  name: string
  platform_url?: string
  username: string
  password: string
  balance_alert_threshold?: number
  max_orders_per_hour?: number
  enabled?: boolean
  remark?: string
  extra_config?: Record<string, unknown>
}

export interface UpdateChargePlatformConfig {
  name?: string
  platform_url?: string
  username?: string
  password?: string
  balance_alert_threshold?: number
  max_orders_per_hour?: number
  enabled?: boolean
  status?: ChargePlatformStatus
  remark?: string
  extra_config?: Record<string, unknown>
}

export interface ChargeSkuMapping {
  id: number
  platform_config_id: number
  platform_config_name?: string
  item_id: string
  spec_value: string | null
  platform_sku_id: string
  platform_sku_name: string | null
  is_active: boolean
  remark: string
  created_at: string
  updated_at: string
}

export interface CreateChargeSkuMapping {
  platform_config_id: number
  item_id: string
  spec_value?: string | null
  platform_sku_id: string
  platform_sku_name?: string | null
  is_active?: boolean
  remark?: string
}

export interface UpdateChargeSkuMapping {
  platform_config_id?: number
  item_id?: string
  spec_value?: string | null
  platform_sku_id?: string
  platform_sku_name?: string | null
  is_active?: boolean
  remark?: string
}

export type ChargeOrderStatus = 'pending' | 'collecting' | 'ready' | 'ordering' | 'success' | 'failed' | 'cancelled'

export interface ChargeOrder {
  id: number
  xy_order_no: string
  xy_account_id: string
  buyer_id: string
  buyer_phone: string
  platform_sku_id: string
  platform_order_id: string | null
  status: ChargeOrderStatus
  retry_count: number
  max_retries: number
  next_retry_at: string | null
  fail_reason: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedResult<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export const getChargePlatformConfigs = async (params?: {
  page?: number
  page_size?: number
  search?: string
}): Promise<PaginatedResult<ChargePlatformConfig>> => {
  const query = new URLSearchParams()
  if (params?.page) query.set('page', String(params.page))
  if (params?.page_size) query.set('page_size', String(params.page_size))
  if (params?.search) query.set('search', params.search)
  const qs = query.toString()
  return get<PaginatedResult<ChargePlatformConfig>>(qs ? `${PREFIX}/configs?${qs}` : `${PREFIX}/configs`)
}

export const getChargePlatformConfig = (id: number): Promise<ChargePlatformConfig> => {
  return get<ChargePlatformConfig>(`${PREFIX}/configs/${id}`)
}

export const createChargePlatformConfig = (data: CreateChargePlatformConfig): Promise<ApiResponse> => {
  return post(`${PREFIX}/configs`, data)
}

export const updateChargePlatformConfig = (id: number, data: UpdateChargePlatformConfig): Promise<ApiResponse> => {
  return put(`${PREFIX}/configs/${id}`, data)
}

export const deleteChargePlatformConfig = (id: number): Promise<ApiResponse> => {
  return del(`${PREFIX}/configs/${id}`)
}

export const getChargeSkuMappings = async (params?: {
  page?: number
  page_size?: number
  item_id?: string
  platform_config_id?: number
}): Promise<PaginatedResult<ChargeSkuMapping>> => {
  const query = new URLSearchParams()
  if (params?.page) query.set('page', String(params.page))
  if (params?.page_size) query.set('page_size', String(params.page_size))
  if (params?.item_id) query.set('item_id', params.item_id)
  if (params?.platform_config_id) query.set('platform_config_id', String(params.platform_config_id))
  const qs = query.toString()
  return get<PaginatedResult<ChargeSkuMapping>>(qs ? `${PREFIX}/sku-mappings?${qs}` : `${PREFIX}/sku-mappings`)
}

export const createChargeSkuMapping = (data: CreateChargeSkuMapping): Promise<ApiResponse> => {
  return post(`${PREFIX}/sku-mappings`, data)
}

export const updateChargeSkuMapping = (id: number, data: UpdateChargeSkuMapping): Promise<ApiResponse> => {
  return put(`${PREFIX}/sku-mappings/${id}`, data)
}

export const deleteChargeSkuMapping = (id: number): Promise<ApiResponse> => {
  return del(`${PREFIX}/sku-mappings/${id}`)
}

export const getChargeOrders = async (params?: {
  page?: number
  page_size?: number
  status?: string
  xy_order_no?: string
}): Promise<PaginatedResult<ChargeOrder>> => {
  const query = new URLSearchParams()
  if (params?.page) query.set('page', String(params.page))
  if (params?.page_size) query.set('page_size', String(params.page_size))
  if (params?.status) query.set('status', params.status)
  if (params?.xy_order_no) query.set('xy_order_no', params.xy_order_no)
  const qs = query.toString()
  return get<PaginatedResult<ChargeOrder>>(qs ? `${PREFIX}/orders?${qs}` : `${PREFIX}/orders`)
}

export const getChargeOrder = (id: number): Promise<ChargeOrder> => {
  return get<ChargeOrder>(`${PREFIX}/orders/${id}`)
}

export const retryChargeOrder = (id: number, resetRetryCount?: boolean): Promise<ApiResponse> => {
  return post(`${PREFIX}/orders/${id}/retry`, { reset_retry_count: resetRetryCount ?? false })
}

export const cancelChargeOrder = (id: number): Promise<ApiResponse> => {
  return post(`${PREFIX}/orders/${id}/cancel`)
}
