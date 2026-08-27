<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const activeTab = ref('file')

// ---- 数据库数据源 ----
const connForm = ref({
  type: 'mysql',
  host: '127.0.0.1',
  port: 3306,
  database: 'dataguard_test',
  username: 'root',
  password: 'root123',
})
const testing = ref(false)
const tables = ref<string[]>([])
const selectedTable = ref('')
const previewRows = ref<any[]>([])
const registered = ref<any>(null)

// ---- 网页数据源 ----
const webUrl = ref('')
const webBatch = ref('')
const webLoading = ref(false)
const webResults = ref<any[]>([])

async function api(path: string, body: any) {
  const resp = await fetch(`/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await resp.json()
  if (!resp.ok) throw new Error(data.detail || '请求失败')
  return data
}

async function testConnection() {
  testing.value = true
  try {
    const data = await api('database/test', connForm.value)
    ElMessage.success(`连接成功（${data.type}）`)
  } catch (e: any) {
    ElMessage.error(String(e.message || e))
  } finally {
    testing.value = false
  }
}

async function loadTables() {
  try {
    const data = await api('database/tables', connForm.value)
    tables.value = data.tables ?? []
    selectedTable.value = ''
    previewRows.value = []
    registered.value = null
  } catch (e: any) {
    ElMessage.error(String(e.message || e))
  }
}

async function onSelectTable() {
  try {
    const data = await api('database/preview', { ...connForm.value, table: selectedTable.value })
    previewRows.value = data.rows ?? []
  } catch (e: any) {
    ElMessage.error(String(e.message || e))
  }
}

async function registerTable() {
  if (!selectedTable.value) return
  try {
    const data = await api('database/register', {
      ...connForm.value,
      table: selectedTable.value,
      name: `mysql.${selectedTable.value}`,
    })
    registered.value = data
    ElMessage.success(`已注册为数据集 ${data.dataset_id}`)
  } catch (e: any) {
    ElMessage.error(String(e.message || e))
  }
}

function goGovernance(datasetId?: string) {
  // 携带新数据集 id 跳转，Workflow 页会针对性选中并清空旧运行状态
  router.push({ path: '/workflow', query: datasetId ? { dataset: datasetId } : {} })
}

async function registerWeb() {
  if (!webUrl.value) return
  webLoading.value = true
  try {
    const data = await api('web/register', { url: webUrl.value })
    webResults.value = [data, ...webResults.value]
    ElMessage.success(`已注册 ${data.filename}`)
  } catch (e: any) {
    ElMessage.error(String(e.message || e))
  } finally {
    webLoading.value = false
  }
}

async function registerBatch() {
  const urls = webBatch.value.split('\n').map((s) => s.trim()).filter(Boolean)
  if (!urls.length) return
  webLoading.value = true
  try {
    const data = await api('web/register_batch', { urls })
    webResults.value = [...(data.registered ?? []), ...webResults.value]
    ElMessage.success(`批量注册完成：${data.count} 个`)
  } catch (e: any) {
    ElMessage.error(String(e.message || e))
  } finally {
    webLoading.value = false
  }
}
</script>

<template>
  <div class="datasource-page">
    <el-card shadow="never">
      <template #header>数据源</template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="文件" name="file">
          <el-empty description="上传 CSV / Excel / JSON 请前往「治理工作台」（左侧菜单）" :image-size="60" />
        </el-tab-pane>

        <el-tab-pane label="数据库" name="database">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form label-width="90px" size="default">
                <el-form-item label="类型">
                  <el-select v-model="connForm.type">
                    <el-option label="MySQL" value="mysql" />
                    <el-option label="PostgreSQL" value="postgresql" />
                  </el-select>
                </el-form-item>
                <el-form-item label="主机">
                  <el-input v-model="connForm.host" />
                </el-form-item>
                <el-form-item label="端口">
                  <el-input-number v-model="connForm.port" :min="1" :max="65535" />
                </el-form-item>
                <el-form-item label="数据库">
                  <el-input v-model="connForm.database" />
                </el-form-item>
                <el-form-item label="用户名">
                  <el-input v-model="connForm.username" />
                </el-form-item>
                <el-form-item label="密码">
                  <el-input v-model="connForm.password" type="password" show-password />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :loading="testing" @click="testConnection">测试连接</el-button>
                  <el-button @click="loadTables">列出表</el-button>
                </el-form-item>
              </el-form>
            </el-col>

            <el-col :span="12">
              <div class="db-tables">
                <div class="section-title">数据表</div>
                <el-select v-model="selectedTable" placeholder="选择表" style="width: 100%" @change="onSelectTable">
                  <el-option v-for="t in tables" :key="t" :label="t" :value="t" />
                </el-select>

                <template v-if="previewRows.length">
                  <div class="section-title">数据预览（前 5 行）</div>
                  <el-table :data="previewRows" size="small" max-height="220">
                    <el-table-column v-for="k in Object.keys(previewRows[0])" :key="k" :prop="k" :label="k" />
                  </el-table>
                </template>

                <el-button v-if="selectedTable" type="success" class="register-btn" @click="registerTable">
                  注册为数据集
                </el-button>
                <el-alert v-if="registered" type="success" :closable="false" class="reg-alert">
                  {{ registered.filename }} → {{ registered.dataset_id }}（只读）
                  <el-button type="primary" link size="small" @click="goGovernance(registered.dataset_id)">前往治理工作台 →</el-button>
                </el-alert>
              </div>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="网页" name="web">
          <div class="web-panel">
            <div class="section-title">单个 URL</div>
            <div class="web-row">
              <el-input v-model="webUrl" placeholder="https://example.com/data" clearable />
              <el-button type="primary" :loading="webLoading" @click="registerWeb">注册</el-button>
            </div>

            <div class="section-title">批量 URL（每行一个）</div>
            <el-input v-model="webBatch" type="textarea" :rows="4" placeholder="https://a.com/1&#10;https://b.com/2" />
            <el-button type="success" class="batch-btn" :loading="webLoading" @click="registerBatch">批量注册</el-button>

            <el-alert v-if="webResults.length" type="success" :closable="false" class="reg-alert">
              <div v-for="r in webResults" :key="r.dataset_id" class="web-result">
                {{ r.filename }} → {{ r.dataset_id }}（{{ r.rows }} 行）
                <el-button type="primary" link size="small" @click="goGovernance(r.dataset_id)">治理 →</el-button>
              </div>
            </el-alert>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.datasource-page {
  max-width: 1100px;
}
.db-tables {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-title {
  font-size: 13px;
  color: #606266;
  font-weight: 600;
}
.register-btn {
  margin-top: 8px;
}
.reg-alert {
  margin-top: 8px;
}
.web-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 640px;
}
.web-row {
  display: flex;
  gap: 8px;
}
.batch-btn {
  align-self: flex-start;
}
.web-result {
  padding: 2px 0;
}
</style>
