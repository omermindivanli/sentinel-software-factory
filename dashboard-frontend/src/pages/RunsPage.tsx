/** Runs List Page */

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Search, Filter, ChevronDown, GitBranch, 
  Clock, DollarSign, Database, Download,
  RefreshCw, Plus
} from 'lucide-react';
import { cn, formatRelativeTime, formatCost, formatTokens, getStatusColor, getPriorityColor } from '../../lib/utils';
import { useFactoryStore } from '../../store/factoryStore';
import { api, queryKeys } from '../../lib/api';
import { useQuery, useQueryClient } from '@tanstack/react-query';

const statusOptions = ['all', 'running', 'completed', 'failed', 'paused', 'cancelled'];
const priorityOptions = ['all', 'critical', 'high', 'medium', 'low'];

export function RunsPage() {
  const { timeRange, runsLoading, runsError, runs, setRuns, setRunsLoading, setRunsError } = useFactoryStore();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [sortBy, setSortBy] = useState<'updated' | 'created' | 'cost' | 'tokens'>('updated');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.runs(50, 0),
    queryFn: () => api.listRuns(50, 0),
    refetchInterval: 15000,
  });
  
  // Sync with store
  React.useEffect(() => {
    if (data?.runs) setRuns(data.runs);
  }, [data, setRuns]);
  
  const filteredRuns = runs
    .filter((run) => {
      if (search) {
        const searchLower = search.toLowerCase();
        return (
          run.work_item.title.toLowerCase().includes(searchLower) ||
          run.work_item.repository.toLowerCase().includes(searchLower) ||
          run.work_item.labels.some(l => l.toLowerCase().includes(searchLower))
        );
      }
      return true;
    })
    .filter((run) => {
      if (statusFilter === 'all') return true;
      return run.status === statusFilter;
    })
    .filter((run) => {
      if (priorityFilter === 'all') return true;
      return run.work_item.priority === priorityFilter;
    })
    .sort((a, b) => {
      let aVal: any, bVal: any;
      switch (sortBy) {
        case 'updated':
          aVal = new Date(a.updated_at).getTime();
          bVal = new Date(b.updated_at).getTime();
          break;
        case 'created':
          aVal = new Date(a.work_item.created_at).getTime();
          bVal = new Date(b.work_item.created_at).getTime();
          break;
        case 'cost':
          aVal = a.metrics.total_cost;
          bVal = b.metrics.total_cost;
          break;
        case 'tokens':
          aVal = a.metrics.total_tokens;
          bVal = b.metrics.total_tokens;
          break;
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    });
  
  const handleSort = (field: typeof sortBy) => {
    if (field === sortBy) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
  };
  
  const SortIcon = ({ field }: { field: typeof sortBy }) => {
    if (sortBy !== field) return <ChevronDown className="w-4 h-4 text-gray-400" />;
    return (
      <ChevronDown 
        className={cn('w-4 h-4', sortDir === 'asc' ? 'rotate-180 text-factory-600' : 'text-factory-600')} 
      />
    );
  };
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Factory Runs</h1>
          <p className="text-gray-500 mt-1">View and manage all factory executions</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => refetch()} disabled={isLoading} className="btn-secondary btn-sm">
            <RefreshCw className={cn('w-4 h-4 mr-2', isLoading ? 'animate-spin' : '')} />
            Refresh
          </button>
          <Link to="/runs/new" className="btn-primary">
            <Plus className="w-4 h-4 mr-2" />
            New Run
          </Link>
        </div>
      </div>
      
      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search runs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-10"
            />
          </div>
          
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input w-auto min-w-[150px]"
          >
            {statusOptions.map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
          
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="input w-auto min-w-[150px]"
          >
            {priorityOptions.map((p) => (
              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>
      
      {/* Results */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-8 h-8 mx-auto text-factory-500 animate-spin mb-4" />
            <p className="text-gray-500">Loading runs...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-500">
            <p>Error loading runs: {error.message}</p>
            <button onClick={() => refetch()} className="btn-secondary btn-sm mt-2">Retry</button>
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="p-12 text-center">
            <GitBranch className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No runs found</h3>
            <p className="text-gray-500 mt-1">Try adjusting your filters or create a new run</p>
          </div>
        ) : (
          <>
            {/* Table Header */}
            <div className="border-b border-gray-200">
              <table className="table">
                <thead>
                  <tr>
                    <th className="cursor-pointer" onClick={() => handleSort('updated')}>
                      Run <SortIcon field="updated" />
                    </th>
                    <th>Work Item</th>
                    <th className="cursor-pointer" onClick={() => handleSort('cost')}>
                      Cost <SortIcon field="cost" />
                    </th>
                    <th className="cursor-pointer" onClick={() => handleSort('tokens')}>
                      Tokens <SortIcon field="tokens" />
                    </th>
                    <th className="cursor-pointer" onClick={() => handleSort('created')}>
                      Created <SortIcon field="created" />
                    </th>
                    <th className="w-32">Actions</th>
                  </tr>
                </thead>
              </table>
            </div>
            
            {/* Table Body */}
            <div className="max-h-[600px] overflow-y-auto">
              <table className="table">
                <tbody>
                  {filteredRuns.map((run) => (
                    <tr key={run.run_id} className="hover:bg-gray-50">
                      <td className="font-mono text-sm text-gray-500">
                        {run.run_id.slice(0, 8)}...
                      </td>
                      <td>
                        <Link to={`/runs/${run.run_id}`} className="font-medium text-gray-900 hover:text-factory-600">
                          {run.work_item.title}
                        </Link>
                        <p className="text-sm text-gray-500 truncate max-w-xs">{run.work_item.repository}</p>
                      </td>
                      <td className="font-mono text-sm text-gray-900">{formatCost(run.metrics.total_cost)}</td>
                      <td className="font-mono text-sm text-gray-900">{formatTokens(run.metrics.total_tokens)}</td>
                      <td className="text-sm text-gray-500">{formatRelativeTime(run.updated_at)}</td>
                      <td>
                        <div className="flex items-center justify-end gap-2">
                          <span className={cn('status-badge', getStatusColor(run.status))}>
                            {run.status.replace('_', ' ')}
                          </span>
                          <span className={cn('badge', getPriorityColor(run.work_item.priority))}>
                            {run.work_item.priority}
                          </span>
                          <Link 
                            to={`/runs/${run.run_id}`} 
                            className="p-1.5 text-gray-400 hover:text-gray-600 rounded"
                            aria-label="View details"
                          >
                            <ChevronDown className="w-4 h-4" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
      
      {/* Pagination placeholder */}
      <div className="flex items-center justify-between px-4 py-3 text-sm text-gray-500">
        <span>Showing {filteredRuns.length} of {runs.length} runs</span>
        <div className="flex gap-2">
          <button className="btn-secondary btn-sm" disabled>Previous</button>
          <button className="btn-secondary btn-sm" disabled>Next</button>
        </div>
      </div>
    </div>
  );
}