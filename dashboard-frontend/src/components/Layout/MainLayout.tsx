/** Main Layout Component */

import React, { useEffect } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  GitBranch, 
  Play, 
  CheckCircle, 
  Box, 
  BookOpen, 
  Activity,
  Settings,
  Menu,
  X,
  Bell,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { cn, formatRelativeTime } from '../lib/utils';
import { useFactoryStore, useWsConnected, useNotifications } from '../store/factoryStore';
import { api } from '../lib/api';
import { NotificationToast } from './NotificationToast';

const navigation = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Runs', href: '/runs', icon: GitBranch },
  { name: 'Triage', href: '/stages/triage', icon: Play },
  { name: 'Planning', href: '/stages/planning', icon: CheckCircle },
  { name: 'Execution', href: '/stages/execution', icon: Box },
  { name: 'Validation', href: '/stages/validation', icon: CheckCircle },
  { name: 'Release', href: '/stages/release', icon: Box },
  { name: 'Documentation', href: '/stages/document', icon: BookOpen },
  { name: 'Monitor', href: '/stages/monitor', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function MainLayout() {
  const location = useLocation();
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useFactoryStore();
  const wsConnected = useWsConnected();
  const notifications = useNotifications();
  
  // Connect WebSocket on mount
  useEffect(() => {
    const handleMessage = (msg: any) => {
      // Handle real-time updates
      console.log('WS message:', msg.type, msg);
    };
    
    api.connectWebSocket(handleMessage);
    api.disconnectWebSocket(); // We'll manage connection per-page
    
    return () => {
      api.disconnectWebSocket();
    };
  }, []);
  
  // Handle keyboard shortcut for sidebar toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar]);

  return (
    <div className="page-container">
      {/* Sidebar */}
      <aside className={cn(
        'sidebar',
        sidebarOpen ? 'sidebar-open' : 'sidebar-closed',
        'lg:sidebar-open'
      )}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-factory-600 rounded-lg flex items-center justify-center">
                <GitBranch className="w-5 h-5 text-white" />
              </div>
              <div className={cn('overflow-hidden transition-all', sidebarOpen ? 'opacity-100' : 'opacity-0 w-0')}>
                <h1 className="font-semibold text-gray-900">Factory</h1>
                <p className="text-xs text-gray-500">Software Factory</p>
              </div>
              <button
                onClick={toggleSidebar}
                className={cn(
                  'ml-auto p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors',
                  sidebarOpen ? 'lg:hidden' : 'hidden'
                )}
                aria-label="Toggle sidebar"
              >
                {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
              </button>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 p-3 space-y-1 overflow-y-auto" role="navigation" aria-label="Main navigation">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href || 
                (item.href !== '/' && location.pathname.startsWith(item.href));
              const Icon = item.icon;
              
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-factory-50 text-factory-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                    !sidebarOpen && 'justify-center px-2'
                  )}
                  title={sidebarOpen ? undefined : item.name}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {sidebarOpen && <span>{item.name}</span>}
                  {isActive && sidebarOpen && (
                    <span className="ml-auto w-1.5 h-1.5 bg-factory-500 rounded-full" />
                  )}
                </NavLink>
              );
            })}
          </nav>
          
          {/* Footer */}
          <div className="p-3 border-t border-gray-200">
            <div className="flex items-center gap-3">
              <div className={cn('w-2 h-2 rounded-full', wsConnected ? 'bg-green-500' : 'bg-red-500')} />
              <span className={cn('text-xs', sidebarOpen ? 'text-gray-500' : 'hidden')}>
                {wsConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </div>
      </aside>
      
      {/* Mobile overlay */}
      {!sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}
      
      {/* Main content */}
      <main className="main-content">
        {/* Top bar */}
        <header className="top-bar">
          <div className="flex items-center justify-between h-16 px-4 lg:px-6">
            <div className="flex items-center gap-4">
              <button
                onClick={toggleSidebar}
                className="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100"
                aria-label="Open menu"
              >
                <Menu className="w-6 h-6" />
              </button>
              <h2 className="text-lg font-semibold text-gray-900 hidden sm:block">
                {navigation.find(n => location.pathname === n.href || location.pathname.startsWith(n.href))?.name || 'Dashboard'}
              </h2>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Notifications */}
              <div className="relative">
                <button
                  className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 relative"
                  aria-label={`Notifications (${notifications.length})`}
                >
                  <Bell className="w-5 h-5" />
                  {notifications.length > 0 && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                      {notifications.length > 9 ? '9+' : notifications.length}
                    </span>
                  )}
                </button>
              </div>
              
              {/* Time range selector */}
              <TimeRangeSelector />
            </div>
          </div>
        </header>
        
        {/* Page content */}
        <div className="p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
      
      {/* Notifications */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {notifications.map((notification) => (
          <NotificationToast key={notification.id} notification={notification} />
        ))}
      </div>
    </div>
  );
}

function TimeRangeSelector() {
  const { timeRange, setTimeRange } = useFactoryStore();
  
  return (
    <select
      value={timeRange}
      onChange={(e) => setTimeRange(e.target.value as any)}
      className="input py-1.5 pr-8 text-sm bg-white"
      aria-label="Time range"
    >
      <option value="1h">Last hour</option>
      <option value="24h">Last 24 hours</option>
      <option value="7d">Last 7 days</option>
      <option value="30d">Last 30 days</option>
    </select>
  );
}