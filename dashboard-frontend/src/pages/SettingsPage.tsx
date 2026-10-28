/** Settings Page */

import React from 'react';
import { 
  Cpu, Database, Network, Shield, Key, 
  Globe, Bell, Palette, Wrench, Save,
  CheckCircle, XCircle
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useFactoryStore } from '../../store/factoryStore';
import { api } from '../../lib/api';

const tabs = [
  { id: 'general', name: 'General', icon: Wrench },
  { id: 'models', name: 'Models', icon: Cpu },
  { id: 'memory', name: 'Memory', icon: Database },
  { id: 'mcp', name: 'MCP Servers', icon: Network },
  { id: 'governance', name: 'Governance', icon: Shield },
  { id: 'secrets', name: 'Secrets', icon: Key },
  { id: 'integrations', name: 'Integrations', icon: Globe },
  { id: 'notifications', name: 'Notifications', icon: Bell },
  { id: 'appearance', name: 'Appearance', icon: Palette },
];

export function SettingsPage() {
  const { timeRange } = useFactoryStore();
  const [activeTab, setActiveTab] = React.useState('general');
  const [config, setConfig] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [message, setMessage] = React.useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  React.useEffect(() => {
    loadConfig();
  }, []);
  
  const loadConfig = async () => {
    try {
      const data = await api.getConfig();
      setConfig(data);
    } catch (error) {
      console.error('Failed to load config:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      // In a real app, would POST to /api/v1/config
      await new Promise(resolve => setTimeout(resolve, 1000));
      setMessage({ type: 'success', text: 'Settings saved successfully' });
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  };
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-factory-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500 mt-1">Configure your software factory</p>
        </div>
        <button 
          onClick={handleSave} 
          disabled={saving}
          className="btn-primary"
        >
          <Save className="w-4 h-4 mr-2" />
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
      
      {message && (
        <div className={cn(
          'p-4 rounded-lg flex items-center gap-3',
          message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
        )}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          <span>{message.text}</span>
        </div>
      )}
      
      <div className="card">
        <div className="flex flex-col lg:flex-row">
          {/* Sidebar */}
          <div className="lg:w-52 border-r border-gray-200 p-4">
            <nav className="space-y-1" role="navigation" aria-label="Settings categories">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-factory-50 text-factory-700'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    )}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />
                    {tab.name}
                  </button>
                );
              })}
            </nav>
          </div>
          
          {/* Content */}
          <div className="flex-1 p-6 overflow-y-auto">
            {renderTabContent(activeTab, config)}
          </div>
        </div>
      </div>
    </div>
  );
}

function renderTabContent(tab: string, config: any) {
  switch (tab) {
    case 'general':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">General Settings</h2>
          <SettingGroup title="Factory Identity">
            <SettingItem label="Factory Name" type="text" placeholder="My Software Factory" />
            <SettingItem label="Environment" type="select" options={[
              { value: 'development', label: 'Development' },
              { value: 'staging', label: 'Staging' },
              { value: 'production', label: 'Production' },
            ]} />
            <SettingItem label="Debug Mode" type="checkbox" />
          </SettingGroup>
          
          <SettingGroup title="API Settings">
            <SettingItem label="API Host" type="text" placeholder="0.0.0.0" />
            <SettingItem label="API Port" type="number" placeholder="8000" />
            <SettingItem label="Dashboard Port" type="number" placeholder="5173" />
          </SettingGroup>
          
          <SettingGroup title="Logging">
            <SettingItem label="Log Level" type="select" options={[
              { value: 'DEBUG', label: 'Debug' },
              { value: 'INFO', label: 'Info' },
              { value: 'WARNING', label: 'Warning' },
              { value: 'ERROR', label: 'Error' },
            ]} />
            <SettingItem label="Log Directory" type="text" placeholder=".factory/logs" />
          </SettingGroup>
        </div>
      );
      
    case 'models':
      return (
        <div className="space-y-6 max-w-3xl">
          <h2 className="text-lg font-semibold text-gray-900">Model Configuration</h2>
          <p className="text-gray-500">Configure models for different agent capabilities</p>
          
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Model ID</th>
                  <th>Provider</th>
                  <th>Capabilities</th>
                  <th>Cost (1k in/out)</th>
                  <th>Max Tokens</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {config?.models?.map((model: any, i: number) => (
                  <tr key={i}>
                    <td className="font-mono">{model.id}</td>
                    <td><span className="badge-blue">{model.provider}</span></td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {model.capabilities?.map((c: string) => (
                          <span key={c} className="badge-gray text-xs">{c}</span>
                        ))}
                      </div>
                    </td>
                    <td className="font-mono text-sm">
                      ${model.cost_per_1k_input}/${model.cost_per_1k_output}
                    </td>
                    <td>{model.max_tokens}</td>
                    <td>
                      <button className="text-factory-600 hover:text-factory-700 text-sm">Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <SettingGroup title="Routing Rules">
            <p className="text-sm text-gray-500 mb-4">Map capabilities to preferred models</p>
            <div className="grid grid-cols-2 gap-4">
              {Object.entries(config?.router?.routing_rules || {}).map(([capability, model]) => (
                <SettingItem key={capability} label={capability} type="select" placeholder="Select model" />
              ))}
            </div>
          </SettingGroup>
        </div>
      );
      
    case 'memory':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">Memory Configuration</h2>
          
          <SettingGroup title="Vector Store (ChromaDB)">
            <SettingItem label="Host" type="text" placeholder="localhost" />
            <SettingItem label="Port" type="number" placeholder="8000" />
            <SettingItem label="Collection Prefix" type="text" placeholder="factory" />
          </SettingGroup>
          
          <SettingGroup title="Graph Store (Neo4j)">
            <SettingItem label="URI" type="text" placeholder="bolt://localhost:7687" />
            <SettingItem label="Username" type="text" placeholder="neo4j" />
            <SettingItem label="Password" type="password" placeholder="••••••••" />
          </SettingGroup>
          
          <SettingGroup title="KV Store (Redis)">
            <SettingItem label="URL" type="text" placeholder="redis://localhost:6379/0" />
          </SettingGroup>
          
          <SettingGroup title="TTL Settings (seconds)">
            <SettingItem label="Working Memory TTL" type="number" placeholder="3600" />
            <SettingItem label="Episodic Memory TTL" type="number" placeholder="2592000" />
          </SettingGroup>
        </div>
      );
      
    case 'mcp':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">MCP Server Configuration</h2>
          <p className="text-gray-500">Configure external Model Context Protocol servers</p>
          
          <SettingGroup title="Connected Servers">
            <div className="space-y-3">
              {config?.mcp?.servers ? Object.entries(config.mcp.servers).map(([name, server]: [string, any]) => (
                <div key={name} className="p-4 border border-gray-200 rounded-lg flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">{name}</h4>
                    <p className="text-sm text-gray-500 font-mono">{server.command} {server.args?.join(' ')}</p>
                  </div>
                  <span className="status-badge status-completed">Connected</span>
                </div>
              )) : (
                <p className="text-gray-500">No MCP servers configured</p>
              )}
            </div>
          </SettingGroup>
          
          <SettingGroup title="Add MCP Server">
            <SettingItem label="Name" type="text" placeholder="github" />
            <SettingItem label="Command" type="text" placeholder="npx" />
            <SettingItem label="Args (JSON)" type="textarea" placeholder='["-y", "@modelcontextprotocol/server-github"]' />
            <SettingItem label="Env Vars (JSON)" type="textarea" placeholder='{"GITHUB_TOKEN": "xxx"}' />
          </SettingGroup>
          
          <SettingGroup title="Progressive Discovery">
            <SettingItem label="Enabled" type="checkbox" />
            <SettingItem label="Context Threshold" type="number" placeholder="0.03" />
          </SettingGroup>
        </div>
      );
      
    case 'governance':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">Governance & Security</h2>
          
          <SettingGroup title="Risk Tiers">
            <p className="text-sm text-gray-500 mb-4">Configure repository risk tiers and required gates</p>
            <div className="space-y-4">
              {config?.governance?.risk_tiers?.map((tier: any, i: number) => (
                <div key={i} className="p-4 border border-gray-200 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-medium capitalize">{tier.name} Risk</h4>
                    <span className={cn('badge', 
                      tier.name === 'high' ? 'badge-red' :
                      tier.name === 'medium' ? 'badge-yellow' : 'badge-green'
                    )}>{tier.max_autonomy}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <SettingItem label="Repo Patterns" type="textarea" placeholder="payments-*, auth-*" />
                    <SettingItem label="Required Gates" type="textarea" placeholder="code_quality, tests, security" />
                  </div>
                  <div className="flex items-center gap-4 mt-3">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="rounded" defaultChecked={tier.human_approval} />
                      <span className="text-sm">Human Approval Required</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input type="checkbox" className="rounded" defaultChecked={tier.require_dual_llm} />
                      <span className="text-sm">Dual LLM Review</span>
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </SettingGroup>
          
          <SettingGroup title="Command Allowlist">
            <SettingItem label="Allowed Commands" type="textarea" placeholder="git, npm, pip, docker..." />
          </SettingGroup>
          
          <SettingGroup title="Command Denylist">
            <SettingItem label="Denied Commands" type="textarea" placeholder="rm -rf, sudo, chmod 777..." />
          </SettingGroup>
          
          <SettingGroup title="Secrets Policy">
            <SettingItem label="Never in Context" type="checkbox" defaultChecked />
            <SettingItem label="Use Env Vars" type="checkbox" defaultChecked />
          </SettingGroup>
        </div>
      );
      
    case 'secrets':
      return (
        <div className="max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Secrets Management</h2>
          <p className="text-gray-500 mb-6">Configure secret storage and access policies. Secrets never enter agent context.</p>
          
          <SettingGroup title="Vault Integration">
            <SettingItem label="Enabled" type="checkbox" />
            <SettingItem label="Vault Address" type="text" placeholder="https://vault.example.com" />
            <SettingItem label="Token Env Var" type="text" placeholder="VAULT_TOKEN" />
          </SettingGroup>
          
          <SettingGroup title="Allowed Secret Patterns">
            <p className="text-sm text-gray-500 mb-3">Regex patterns for secret names allowed in configuration</p>
            <div className="space-y-2">
              {['TOKEN$', 'KEY$', 'SECRET$', 'PASSWORD$'].map((pattern) => (
                <div key={pattern} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                  <code className="text-sm">{pattern}</code>
                  <span className="badge-green">Allowed</span>
                </div>
              ))}
            </div>
          </SettingGroup>
          
          <SettingGroup title="Blocked in Context">
            <p className="text-sm text-gray-500 mb-3">Keywords that trigger secret detection in agent context</p>
            <div className="flex flex-wrap gap-2">
              {['password', 'secret', 'token', 'key', 'credential', 'api_key', 'apikey', 'auth', 'bearer', 'private'].map((word) => (
                <span key={word} className="badge-red">{word}</span>
              ))}
            </div>
          </SettingGroup>
        </div>
      );
      
    case 'integrations':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">Integrations</h2>
          <p className="text-gray-500 mb-6">Configure external service integrations</p>
          
          {['GitHub', 'GitLab', 'Linear', 'Jira', 'Slack', 'PagerDuty', 'Datadog'].map((service) => (
            <SettingGroup key={service} title={service}>
              <SettingItem label="Enabled" type="checkbox" />
              <SettingItem label="API Token" type="password" placeholder="••••••••" />
              <SettingItem label="Webhook URL" type="text" placeholder="https://..." />
            </SettingGroup>
          ))}
        </div>
      );
      
    case 'notifications':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">Notifications</h2>
          
          <SettingGroup title="Email Notifications">
            <SettingItem label="Enabled" type="checkbox" />
            <SettingItem label="Email Address" type="email" placeholder="user@example.com" />
            <SettingItem label="Notify on Run Complete" type="checkbox" defaultChecked />
            <SettingItem label="Notify on Run Failed" type="checkbox" defaultChecked />
            <SettingItem label="Notify on Checkpoint Required" type="checkbox" defaultChecked />
          </SettingGroup>
          
          <SettingGroup title="Slack Notifications">
            <SettingItem label="Enabled" type="checkbox" />
            <SettingItem label="Webhook URL" type="text" placeholder="https://hooks.slack.com/..." />
            <SettingItem label="Channel" type="text" placeholder="#factory-alerts" />
          </SettingGroup>
          
          <SettingGroup title="Webhook Notifications">
            <SettingItem label="Enabled" type="checkbox" />
            <SettingItem label="URL" type="text" placeholder="https://your-webhook.example.com" />
            <SettingItem label="Events" type="textarea" placeholder="run.completed, run.failed, checkpoint.required" />
          </SettingGroup>
        </div>
      );
      
    case 'appearance':
      return (
        <div className="space-y-6 max-w-2xl">
          <h2 className="text-lg font-semibold text-gray-900">Appearance</h2>
          
          <SettingGroup title="Theme">
            <SettingItem label="Color Scheme" type="select" options={[
              { value: 'light', label: 'Light' },
              { value: 'dark', label: 'Dark' },
              { value: 'system', label: 'System' },
            ]} />
            <SettingItem label="Accent Color" type="select" options={[
              { value: 'factory', label: 'Factory Blue' },
              { value: 'emerald', label: 'Emerald' },
              { value: 'violet', label: 'Violet' },
              { value: 'amber', label: 'Amber' },
            ]} />
          </SettingGroup>
          
          <SettingGroup title="Density">
            <SettingItem label="Compact Mode" type="checkbox" />
            <SettingItem label="Show Animations" type="checkbox" defaultChecked />
          </SettingGroup>
          
          <SettingGroup title="Sidebar">
            <SettingItem label="Default Open" type="checkbox" defaultChecked />
            <SettingItem label="Show Tooltips on Collapse" type="checkbox" defaultChecked />
          </SettingGroup>
        </div>
      );
      
    default:
      return <div>Select a tab</div>;
  }
}

function SettingGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-200 rounded-lg p-6">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">{title}</h3>
      {children}
    </div>
  );
}

function SettingItem({ 
  label, 
  type = 'text', 
  placeholder, 
  options, 
  defaultChecked,
}: { 
  label: string; 
  type?: 'text' | 'number' | 'email' | 'password' | 'textarea' | 'select' | 'checkbox';
  placeholder?: string;
  options?: { value: string; label: string }[];
  defaultChecked?: boolean;
}) {
  if (type === 'checkbox') {
    return (
      <label className="flex items-center gap-3">
        <input 
          type="checkbox" 
          className="w-4 h-4 rounded border-gray-300 text-factory-600 focus:ring-factory-500" 
          defaultChecked={defaultChecked}
        />
        <span className="text-sm text-gray-700">{label}</span>
      </label>
    );
  }
  
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {type === 'select' && options ? (
        <select className="input" defaultValue={options[0]?.value}>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea className="input min-h-[80px] resize-y" placeholder={placeholder} />
      ) : (
        <input 
          type={type} 
          className="input" 
          placeholder={placeholder} 
        />
      )}
    </div>
  );
}