"use client";
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8080';

interface GitHubCloneModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onSuccess: (repoName: string) => void;
}

interface Repository {
  name: string;
  full_name: string;
  description: string;
  html_url: string;
  clone_url: string;
  ssh_url: string;
  stars: number;
  forks: number;
  language?: string;
  updated_at: string;
  owner: {
    login: string;
    avatar_url: string;
  };
  private: boolean;
  default_branch: string;
}

export default function GitHubCloneModal({
  isOpen,
  onClose,
  projectId,
  onSuccess
}: GitHubCloneModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [searchTab, setSearchTab] = useState<'search' | 'my-repos' | 'url'>('search');
  const [customUrl, setCustomUrl] = useState('');
  const [totalCount, setTotalCount] = useState(0);
  const [error, setError] = useState('');
  const [userRepos, setUserRepos] = useState<Repository[]>([]);
  const [isLoadingUserRepos, setIsLoadingUserRepos] = useState(false);

  const searchRepositories = async () => {
    if (!searchQuery.trim()) return;
    
    setIsSearching(true);
    setError('');
    
    try {
      const response = await fetch(
        `${API_BASE}/api/github/search?query=${encodeURIComponent(searchQuery)}&per_page=20`
      );
      
      if (response.ok) {
        const data = await response.json();
        setRepositories(data.repositories);
        setTotalCount(data.total_count);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to search repositories');
      }
    } catch (error) {
      setError('Failed to search repositories');
    } finally {
      setIsSearching(false);
    }
  };

  const cloneRepository = async (repo: Repository) => {
    setIsCloning(true);
    setError('');
    
    try {
      const response = await fetch(`${API_BASE}/api/projects/${projectId}/github/clone`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          clone_url: repo.clone_url,
          repo_name: repo.name
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        onSuccess(result.repo_name);
        onClose();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to clone repository');
      }
    } catch (error) {
      setError('Failed to clone repository');
    } finally {
      setIsCloning(false);
    }
  };

  const cloneFromUrl = async () => {
    if (!customUrl.trim()) return;
    
    // Extract repo name from URL
    const urlMatch = customUrl.match(/github\.com\/[^\/]+\/([^\/]+?)(?:\.git)?(?:\/|$)/);
    if (!urlMatch) {
      setError('Invalid GitHub URL format');
      return;
    }
    
    const repoName = urlMatch[1];
    setIsCloning(true);
    setError('');
    
    try {
      const response = await fetch(`${API_BASE}/api/projects/${projectId}/github/clone`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          clone_url: customUrl.endsWith('.git') ? customUrl : `${customUrl}.git`,
          repo_name: repoName
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        onSuccess(result.repo_name);
        onClose();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to clone repository');
      }
    } catch (error) {
      setError('Failed to clone repository');
    } finally {
      setIsCloning(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (searchTab === 'search') {
        searchRepositories();
      } else if (searchTab === 'url') {
        cloneFromUrl();
      }
    }
  };

  const fetchUserRepositories = async () => {
    setIsLoadingUserRepos(true);
    setError('');
    
    try {
      const response = await fetch(`${API_BASE}/api/github/user/repos?per_page=50`);
      
      if (response.ok) {
        const data = await response.json();
        setUserRepos(data.repositories);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to fetch your repositories');
      }
    } catch (error) {
      setError('Failed to fetch your repositories');
    } finally {
      setIsLoadingUserRepos(false);
    }
  };

  const selectRepository = (repo: Repository) => {
    // Auto-populate URL field and switch to URL tab
    setCustomUrl(repo.clone_url);
    setSearchTab('url');
  };

  // Fetch user repos when My Repositories tab is selected
  useEffect(() => {
    if (searchTab === 'my-repos' && userRepos.length === 0 && !isLoadingUserRepos) {
      fetchUserRepositories();
    }
  }, [searchTab]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24));
    
    if (diffInDays === 0) {
      return 'Today';
    } else if (diffInDays === 1) {
      return 'Yesterday';
    } else if (diffInDays < 30) {
      return `${diffInDays} days ago`;
    } else if (diffInDays < 365) {
      const months = Math.floor(diffInDays / 30);
      return `${months} month${months > 1 ? 's' : ''} ago`;
    } else {
      const years = Math.floor(diffInDays / 365);
      return `${years} year${years > 1 ? 's' : ''} ago`;
    }
  };

  const resetModal = () => {
    setSearchQuery('');
    setRepositories([]);
    setSelectedRepo(null);
    setCustomUrl('');
    setError('');
    setTotalCount(0);
    setUserRepos([]);
  };

  useEffect(() => {
    if (!isOpen) {
      resetModal();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
      >
        <div 
          className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-4xl mx-4 max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
        {/* Header */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Clone GitHub Repository</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              ✕
            </button>
          </div>
          
          {/* Tab Navigation */}
          <div className="flex space-x-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => setSearchTab('search')}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                searchTab === 'search'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              🔍 Search Repositories
            </button>
            <button
              onClick={() => setSearchTab('my-repos')}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                searchTab === 'my-repos'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              📚 My Repositories
            </button>
            <button
              onClick={() => setSearchTab('url')}
              className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                searchTab === 'url'
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white shadow'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              🔗 Clone from URL
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {searchTab === 'search' ? (
            <div className="h-full flex flex-col">
              {/* Search Input */}
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Search repositories (e.g., 'react router', 'user:facebook')"
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={searchRepositories}
                    disabled={isSearching || !searchQuery.trim()}
                    className="px-6 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg font-medium"
                  >
                    {isSearching ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      'Search'
                    )}
                  </button>
                </div>
                {totalCount > 0 && (
                  <p className="text-sm text-gray-500 mt-2">
                    Found {totalCount.toLocaleString()} repositories
                  </p>
                )}
              </div>

              {/* Search Results */}
              <div className="flex-1 overflow-y-auto p-6">
                {error && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg mb-4">
                    {error}
                  </div>
                )}

                {repositories.length === 0 && !isSearching && searchQuery && (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-6xl mb-4">🔍</div>
                    <p>No repositories found for "{searchQuery}"</p>
                    <p className="text-sm mt-2">Try different keywords or check your spelling</p>
                  </div>
                )}

                {repositories.length === 0 && !searchQuery && (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-6xl mb-4">📚</div>
                    <p>Search for repositories to clone</p>
                    <p className="text-sm mt-2">Enter keywords, language names, or specific repository names</p>
                  </div>
                )}

                <div className="space-y-3">
                  {repositories.map((repo) => (
                    <div
                      key={repo.full_name}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 mb-2">
                            <img
                              src={repo.owner.avatar_url}
                              alt={repo.owner.login}
                              className="w-8 h-8 rounded-full"
                            />
                            <div className="min-w-0">
                              <h3 className="font-semibold text-blue-600 dark:text-blue-400 truncate">
                                {repo.full_name}
                              </h3>
                              <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                                <span className="flex items-center gap-1">
                                  ⭐ {repo.stars.toLocaleString()}
                                </span>
                                <span className="flex items-center gap-1">
                                  🍴 {repo.forks.toLocaleString()}
                                </span>
                                {repo.language && (
                                  <span className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs">
                                    {repo.language}
                                  </span>
                                )}
                                <span>Updated {formatDate(repo.updated_at)}</span>
                              </div>
                            </div>
                          </div>
                          
                          {repo.description && (
                            <p className="text-gray-600 dark:text-gray-400 text-sm mb-3 line-clamp-2">
                              {repo.description}
                            </p>
                          )}
                          
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            {repo.private && (
                              <span className="bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 px-2 py-1 rounded">
                                Private
                              </span>
                            )}
                            <span className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                              {repo.default_branch}
                            </span>
                          </div>
                        </div>
                        
                        <div className="ml-4 flex flex-col gap-2">
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 text-sm"
                          >
                            View →
                          </a>
                          <button
                            onClick={() => cloneRepository(repo)}
                            disabled={isCloning}
                            className="px-4 py-2 bg-green-500 hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded text-sm font-medium"
                          >
                            {isCloning ? (
                              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                            ) : (
                              'Clone'
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : searchTab === 'my-repos' ? (
            // My Repositories tab
            <div className="h-full flex flex-col">
              {/* Header */}
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-medium mb-2">Your GitHub Repositories</h3>
                <p className="text-sm text-gray-500">
                  Select a repository to auto-populate the clone URL
                </p>
              </div>

              {/* My Repositories List */}
              <div className="flex-1 overflow-y-auto p-6">
                {error && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg mb-4">
                    {error}
                  </div>
                )}

                {isLoadingUserRepos && (
                  <div className="text-center py-12">
                    <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-500">Loading your repositories...</p>
                  </div>
                )}

                {userRepos.length === 0 && !isLoadingUserRepos && !error && (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-6xl mb-4">📚</div>
                    <p>No repositories found</p>
                    <p className="text-sm mt-2">Create some repositories on GitHub to see them here</p>
                  </div>
                )}

                <div className="space-y-3">
                  {userRepos.map((repo) => (
                    <div
                      key={repo.full_name}
                      className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-600 transition-colors cursor-pointer"
                      onClick={() => selectRepository(repo)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 mb-2">
                            <img
                              src={repo.owner.avatar_url}
                              alt={repo.owner.login}
                              className="w-8 h-8 rounded-full"
                            />
                            <div className="min-w-0">
                              <h3 className="font-semibold text-blue-600 dark:text-blue-400 truncate">
                                {repo.full_name}
                              </h3>
                              <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                                <span className="flex items-center gap-1">
                                  ⭐ {repo.stars.toLocaleString()}
                                </span>
                                <span className="flex items-center gap-1">
                                  🍴 {repo.forks.toLocaleString()}
                                </span>
                                {repo.language && (
                                  <span className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-xs">
                                    {repo.language}
                                  </span>
                                )}
                                <span>Updated {formatDate(repo.updated_at)}</span>
                              </div>
                            </div>
                          </div>
                          
                          {repo.description && (
                            <p className="text-gray-600 dark:text-gray-400 text-sm mb-3 line-clamp-2">
                              {repo.description}
                            </p>
                          )}
                          
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            {repo.private && (
                              <span className="bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 px-2 py-1 rounded">
                                Private
                              </span>
                            )}
                            <span className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                              {repo.default_branch}
                            </span>
                          </div>
                        </div>
                        
                        <div className="ml-4 flex flex-col gap-2">
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 text-sm"
                          >
                            View →
                          </a>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              selectRepository(repo);
                            }}
                            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded text-sm font-medium"
                          >
                            Select
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            // Clone from URL tab
            <div className="p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    GitHub Repository URL
                  </label>
                  <input
                    type="url"
                    value={customUrl}
                    onChange={(e) => setCustomUrl(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="https://github.com/username/repository"
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-sm text-gray-500 mt-2">
                    Enter the full URL of a GitHub repository to clone it
                  </p>
                </div>

                {error && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
                    {error}
                  </div>
                )}

                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                  <h4 className="font-medium mb-2">Supported URL formats:</h4>
                  <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                    <li>• https://github.com/username/repository</li>
                    <li>• https://github.com/username/repository.git</li>
                    <li>• git@github.com:username/repository.git (SSH)</li>
                  </ul>
                </div>

                <button
                  onClick={cloneFromUrl}
                  disabled={isCloning || !customUrl.trim()}
                  className="w-full py-3 bg-green-500 hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg font-medium flex items-center justify-center gap-2"
                >
                  {isCloning ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      Cloning...
                    </>
                  ) : (
                    <>
                      📥 Clone Repository
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
        </div>
      </motion.div>
      </div>
    </motion.div>
  );
}