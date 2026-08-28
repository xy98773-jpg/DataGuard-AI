<script setup lang="ts">
// 模型设置：可视化配置 LLM（保存即热生效，无需重启后端）
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

const form = ref({
  provider: 'openai_compatible',
  model: '',
  api_key: '',
  base_url: '',
  temperature: 0,
  max_tokens: 4096,
  fallback_model: '',
  fallback_base_url: '',
  fallback_api_key: '',
})
const maskedKey = ref('')
const fallbackMaskedKey = ref('')
const configured = ref(false)
const updatedAt = ref('')
const loading = ref(false)
const testing = ref(false)
const testResult = ref('')

// 常见模型快捷选择
const PRESETS: Record<string, { model: string; base_url: string; hint: string }[]> = {
  阿里百炼: [
    { model: 'qwen-flash', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', hint: '免费高速，适合日常测试' },
    { model: 'qwen-max', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', hint: '旗舰版，质量更高' },
  ],
  DeepSeek: [
    { model: 'deepseek-chat', base_url: 'https://api.deepseek.com/v1', hint: 'V3 通用对话' },
    { model: 'deepseek-reasoner', base_url: 'https://api.deepseek.com/v1', hint: 'R1 推理模型' },
  ],
  OpenAI: [
    { model: 'gpt-4o-mini', base_url: 'https://api.openai.com/v1', hint: '轻量快速' },
    { model: 'gpt-4o', base_url: 'https://api.openai.com/v1', hint: '旗舰' },
  ],
  自定义: [{ model: '', base_url: '', hint: '任意 OpenAI 兼容接口' }],
}
const providers = ['阿里百炼', 'DeepSeek', 'OpenAI', '自定义']

async function load() {
  loading.value = true
  try {
    const resp = await fetch('/api/settings/llm')
    const d = await resp.json()
    form.value.provider = providers.find((p) => PRESETS[p].some((x) => x.model === d.model && x.base_url === d.base_url)) || '自定义'
    form.value.model = d.model
    form.value.base_url = d.base_url
    form.value.temperature = d.temperature ?? 0
    form.value.max_tokens = d.max_tokens ?? 4096
    form.value.fallback_model = d.fallback_model ?? ''
    form.value.fallback_base_url = d.fallback_base_url ?? ''
    maskedKey.value = d.api_key_masked ?? ''
    fallbackMaskedKey.value = d.fallback_api_key_masked ?? ''
    configured.value = !!d.configured
    updatedAt.value = d.updated_at ?? ''
    form.value.api_key = ''
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

function applyPreset() {
  const preset = PRESETS[form.value.provider]?.[0]
  if (preset && preset.model) {
    form.value.model = preset.model
    form.value.base_url = preset.base_url
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = ''
  try {
    const resp = await fetch('/api/settings/llm/test', { method: 'POST' })
    const d = await resp.json()
    if (resp.ok) {
      testResult.value = `✅ 连接成功（${d.elapsed}s）模型 ${d.model} 回复：${d.reply}`
      ElMessage.success('连接成功')
    } else {
      testResult.value = `❌ ${d.detail ?? '连接失败'}`
      ElMessage.error('连接失败')
    }
  } catch {
    testResult.value = '❌ 请求异常（后端不可用）'
    ElMessage.error('请求异常')
  } finally {
    testing.value = false
  }
}

async function save() {
  if (!form.value.model.trim()) return ElMessage.warning('请填写模型名称')
  if (!form.value.base_url.trim()) return ElMessage.warning('请填写 API 地址（Base URL）')
  loading.value = true
  try {
    const resp = await fetch('/api/settings/llm', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('dg_token') ?? ''}`,
      },
      body: JSON.stringify(form.value),
    })
    const d = await resp.json()
    if (!resp.ok) {
      if (resp.status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        setTimeout(() => (window.location.href = '/login'), 800)
        return
      }
      ElMessage.error(d.detail || '保存失败')
      return
    }
    maskedKey.value = d.api_key_masked ?? maskedKey.value
    configured.value = true
    updatedAt.value = d.updated_at ?? ''
    form.value.api_key = ''
    ElMessage.success('已保存，下次治理立即生效（无需重启）')
    await load()
  } catch {
    ElMessage.error('保存失败（后端不可用）')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-page">
    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="settings-head">
          <span>模型设置（LLM）</span>
          <span class="settings-tip">保存后立即生效，无需重启后端</span>
        </div>
      </template>

      <el-form label-width="130px" style="max-width: 720px">
        <el-form-item label="服务商">
          <el-select v-model="form.provider" style="width: 300px" @change="applyPreset">
            <el-option v-for="p in providers" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>

        <el-form-item label="模型名称">
          <el-input v-model="form.model" placeholder="如 qwen-flash / deepseek-chat / gpt-4o-mini" style="width: 300px" />
          <div class="preset-hint" v-if="PRESETS[form.provider]?.[0]?.hint">
            {{ PRESETS[form.provider][0].hint }}
          </div>
        </el-form-item>

        <el-form-item label="API 地址 (Base URL)">
          <el-input v-model="form.base_url" placeholder="https://.../v1" style="width: 460px" />
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="configured ? `已配置（${maskedKey}），留空则保持不变` : '请输入 API Key'"
            style="width: 460px"
          />
        </el-form-item>

        <el-form-item label="温度 Temperature">
          <el-slider v-model="form.temperature" :min="0" :max="1.5" :step="0.1" style="width: 300px" />
          <span class="temp-val">{{ form.temperature.toFixed(1) }}</span>
        </el-form-item>

        <el-form-item label="最大 Token">
          <el-input-number v-model="form.max_tokens" :min="256" :max="32768" :step="512" />
        </el-form-item>

        <el-divider content-position="left">备用模型（主模型失败自动切换）</el-divider>

        <el-form-item label="备用模型名称">
          <el-input v-model="form.fallback_model" placeholder="如 qwen-turbo（百炼，低成本）" style="width: 300px" />
          <div class="preset-hint">主模型调用失败时自动切换到备用模型，提升鲁棒性</div>
        </el-form-item>

        <el-form-item label="备用 API 地址">
          <el-input v-model="form.fallback_base_url" placeholder="https://.../v1" style="width: 460px" />
        </el-form-item>

        <el-form-item label="备用 API Key">
          <el-input
            v-model="form.fallback_api_key"
            type="password"
            show-password
            :placeholder="fallbackMaskedKey ? `已配置（${fallbackMaskedKey}），留空则保持不变` : '留空则复用主 Key'"
            style="width: 460px"
          />
        </el-form-item>

        <div class="free-models-tip">
          💡 <b>百炼免费/低成本模型（同 Key 可用）</b>：<code>qwen-flash</code>（长期限免，推荐主模型）、<code>qwen-turbo</code>（低成本，推荐备用）、<code>qwen-plus</code>（含免费额度）。来源：阿里云百炼官方「模型大全功能规格与计费」。
        </div>

        <el-form-item style="margin-top: 12px">
          <el-button type="primary" :loading="loading" @click="save">保存配置</el-button>
          <el-button :loading="testing" @click="testConnection">测试连接</el-button>
        </el-form-item>
      </el-form>

      <div v-if="testResult" class="test-result" :class="testResult.startsWith('✅') ? 'ok' : 'bad'">{{ testResult }}</div>
      <div v-if="updatedAt" class="updated-at">最近保存：{{ updatedAt }}（当前生效模型：{{ form.model }}）</div>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 960px;
}
.settings-card {
  margin-top: 4px;
}
.settings-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.settings-tip {
  font-size: 12px;
  color: #909399;
}
.preset-hint {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}
.temp-val {
  margin-left: 10px;
  color: #606266;
  font-weight: 600;
}
.test-result {
  margin-top: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
}
.test-result.ok {
  background: #f0f9eb;
  color: #67c23a;
}
.test-result.bad {
  background: #fef0f0;
  color: #f56c6c;
}
.updated-at {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}
.free-models-tip {
  margin: 4px 0 14px 130px;
  padding: 10px 14px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 6px;
  font-size: 12px;
  color: #529b2e;
  line-height: 1.8;
}
.free-models-tip code {
  background: #fff;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid #e1f3d8;
}
</style>
