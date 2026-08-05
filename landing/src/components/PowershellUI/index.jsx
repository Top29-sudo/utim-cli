import React, { useState, useEffect, useRef } from 'react';
import { getApiUrl } from '../../lib/api';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { InlineFeatures, InlinePricing, InlineAbout, InlineConnect, InlineDocs, InlineHighlights, InlineChangelog, InlineReferral } from './TerminalWidgets';
import aboutMd from '../../docs_md/about.md?raw';
import changelogMd from '../../docs_md/changelog.md?raw';
import docsMd from '../../docs_md/docs.md?raw';
import featuresMd from '../../docs_md/features.md?raw';
import licenseMd from '../../docs_md/license.md?raw';
import pricingMd from '../../docs_md/pricing.md?raw';
import privacyMd from '../../docs_md/privacy.md?raw';
import refundMd from '../../docs_md/refund.md?raw';
import supportMd from '../../docs_md/support.md?raw';
import termsMd from '../../docs_md/terms.md?raw';
import activateMd from '../../docs_md/activate.md?raw';
import authMd from '../../docs_md/auth.md?raw';
import profileMd from '../../docs_md/profile.md?raw';
import referralMd from '../../docs_md/referral.md?raw';
import ReactMarkdown from 'react-markdown';
import PromoModal from '../PromoModal';
import './PowershellUI.css';

const MD_FILES = {
  about: aboutMd,
  changelog: changelogMd,
  docs: docsMd,
  features: featuresMd,
  license: licenseMd,
  pricing: pricingMd,
  privacy: privacyMd,
  refund: refundMd,
  support: supportMd,
  terms: termsMd,
  activate: activateMd,
  auth: authMd,
  profile: profileMd,
  referral: referralMd
};

const PromotionalBanner = ({ onOpenModal }) => {
  const [isDismissed, setIsDismissed] = useState(() => {
    try {
      return localStorage.getItem('utim_v2_banner_closed') === 'true';
    } catch (e) {
      return false;
    }
  });

  const handleDismiss = (e) => {
    e.stopPropagation();
    setIsDismissed(true);
    try {
      localStorage.setItem('utim_v2_banner_closed', 'true');
    } catch (err) {}
  };

  if (isDismissed) return null;

  return (
    <div className="term-support-disclaimer term-promo-banner" style={{ borderTop: 'none', background: 'linear-gradient(90deg, rgba(166,227,161,0.2) 0%, rgba(203,166,247,0.2) 100%)', borderColor: '#a6e3a1' }}>
      <div className="ts-badge" style={{ backgroundColor: '#a6e3a1', color: '#111', fontWeight: 'bold' }}>
        🚀 UTIM V2 LIVE
      </div>
      <div className="ts-text" style={{ color: '#cdd6f4' }}>
        <strong>UTIM v2 is live!</strong> Install it with <code style={{ background: '#313244', padding: '2px 8px', borderRadius: '4px', color: '#a6e3a1', fontFamily: 'monospace' }}>npm install -g @emend-ai/utim</code>
      </div>
      <div className="ts-npm-pill" style={{ backgroundColor: '#1e1e2e', borderColor: '#a6e3a1', color: '#a6e3a1' }}>
        <strong>v2.0.0</strong>
      </div>
      <button 
        className="ts-close-btn" 
        onClick={handleDismiss}
        title="Close banner"
        aria-label="Close banner"
      >
        ✕
      </button>
    </div>
  );
};

const asciiArt = `
██╗   ██╗████████╗██╗███╗   ███╗     █████╗ ██╗    ███████╗██╗   ██╗██████╗ ██████╗  ██████╗ ██████╗ ████████╗
██║   ██║╚══██╔══╝██║████╗ ████║    ██╔══██╗██║    ██╔════╝██║   ██║██╔══██╗██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝
██║   ██║   ██║   ██║██╔████╔██║    ███████║██║    ███████╗██║   ██║██████╔╝██████╔╝██║   ██║██████╔╝   ██║   
██║   ██║   ██║   ██║██║╚██╔╝██║    ██╔══██║██║    ╚════██║██║   ██║██╔═══╝ ██╔═══╝ ██║   ██║██╔══██╗   ██║   
╚██████╔╝   ██║   ██║██║ ╚═╝ ██║    ██║  ██║██║    ███████║╚██████╔╝██║     ██║     ╚██████╔╝██║  ██║   ██║   
 ╚═════╝    ╚═╝   ╚═╝╚═╝     ╚═╝    ╚═╝  ╚═╝╚═╝    ╚══════╝ ╚═════╝ ╚═╝     ╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
`;
const getInitialHistory = (user, userProfile, version = '2.1.0') => {
  const userEmail = user?.email || 'local@utim.dev';
  const rawPlan = userProfile?.plan || 'free';
  const planDisplayName = rawPlan === 'free' ? 'Community' : (rawPlan.charAt(0).toUpperCase() + rawPlan.slice(1));
  const userType = `UTIM ${planDisplayName}`;
  const bannerLine = `${userEmail}  •  ${userType}`;

  return [
    { type: 'command', text: 'PS C:\\projects\\utim> utim' },
    { type: 'ascii', text: asciiArt },
    { type: 'text', text: `UTIM AI "SUPPORT" (Web Assistant) v${version}`, color: '#a6e3a1' },
    { type: 'banner' },
    { type: 'empty' },
    { type: 'box', text: [
        "============= UTIM V2 IS LIVE! =============",
        "  🎉 RELEASE:  UTIM v2.0 is live! Install with: npm install -g @emend-ai/utim",
        "  ℹ️ NOTICE:   This web chat is the UTIM AI \"SUPPORT\" Assistant.",
        "              To let UTIM build applications, edit code, and run shell",
        "              commands, install the CLI locally on your machine.",
        "  📦 Install:  npm install -g @emend-ai/utim",
        "  🚀 Run CLI:  utim \"build a react dashboard\"",
        "  🏪 MARKET:   Creators Ecosystem — browse, install & publish skills/miniagents!"
      ]
    },
    { type: 'empty' },
    { type: 'component', name: 'Highlights' },
    { type: 'empty' },
  ];
};

const SLASH_COMMANDS = [
  { cmd: '/home', desc: 'Navigate to Homepage' },
  { cmd: '/features', desc: 'List UTIM capabilities' },
  { cmd: '/changelog', desc: 'View version release history' },
  { cmd: '/about', desc: 'About the architects' },
  { cmd: '/pricing', desc: 'View subscription tiers' },
  { cmd: '/docs', desc: 'Read the documentation' },
  { cmd: '/referral', desc: 'Earn free access via referrals' },
  { cmd: '/contacts', desc: 'Get in touch & social networks' },
  { cmd: '/login', desc: 'Login to your account' },
  { cmd: '/clear', desc: 'Clear console history' }
];

const CodeBlockContainer = ({ code, lang }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="term-codeblock-container">
      <div className="term-codeblock-header">
        <span className="term-codeblock-lang">{lang || 'code'}</span>
        <button className="term-codeblock-copy-btn" onClick={handleCopy}>
          {copied ? (
            <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
              ✓ Copied!
            </span>
          ) : (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              Copy code
            </span>
          )}
        </button>
      </div>
      <pre className="term-codeblock-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
};

const PowershellUI = () => {
  const { isAuthenticated, user, userProfile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [cliVersion, setCliVersion] = useState('2.1.0');
  const [history, setHistory] = useState(() => getInitialHistory(user, userProfile, '2.1.0'));
  const [input, setInput] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeTab, setActiveTab] = useState('/home');
  const [chatMessages, setChatMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showSupportBanner, setShowSupportBanner] = useState(() => {
    try {
      return localStorage.getItem('utim_support_banner_closed') !== 'true';
    } catch (e) {
      return true;
    }
  });

  const handleCloseSupportBanner = () => {
    setShowSupportBanner(false);
    try {
      localStorage.setItem('utim_support_banner_closed', 'true');
    } catch (err) {}
  };
  const [npmBannerCopied, setNpmBannerCopied] = useState(false);
  const [isPromoModalOpen, setIsPromoModalOpen] = useState(false);
  const [isAndroid, setIsAndroid] = useState(false);

  useEffect(() => {
    if (typeof navigator !== 'undefined' && /android/i.test(navigator.userAgent)) {
      setIsAndroid(true);
      document.body.classList.add('termux-mode');
    }
    return () => {
      document.body.classList.remove('termux-mode');
    };
  }, []);

  const handleCopyNpmBanner = (e) => {
    e.stopPropagation();
    navigator.clipboard.writeText("npm install -g @emend-ai/utim");
    setNpmBannerCopied(true);
    setTimeout(() => setNpmBannerCopied(false), 2000);
  };
  
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const contentRef = useRef(null);
  const shouldScrollToBottom = useRef(true);

  // Sync history and active tab with the URL path
  useEffect(() => {
    const path = location.pathname;
    let targetCmd = '/home';
    if (path === '/features') targetCmd = '/features';
    else if (path === '/about') targetCmd = '/about';
    else if (path === '/pricing') targetCmd = '/pricing';
    else if (path === '/changelog') targetCmd = '/changelog';
    else if (path === '/referral' || path === '/referrals') targetCmd = '/referral';
    else if (path === '/docs' || path === '/terms' || path === '/privacy' || path === '/license' || path === '/refund') targetCmd = '/docs';
    else if (path === '/contacts' || path === '/support' || path === '/connect') targetCmd = '/contacts';
    
    setActiveTab(targetCmd);

    // Dynamic SEO Title and Meta Description Updates per tab
    const seoTitles = {
      '/home': 'UTIM AI v2.0 – Elite Autonomous AI Coding Agent & Creators Marketplace',
      '/features': 'Features | UTIM AI v2.0 – Creators Ecosystem & AI Agent Capabilities',
      '/pricing': 'Pricing & Plans | UTIM AI – Flexible Credits & BYOK Models',
      '/docs': 'Documentation | UTIM AI CLI v2.0 Setup & Command Reference',
      '/changelog': 'Changelog & Release Notes | UTIM AI v2.0 Updates',
      '/about': 'About UTIM AI – Architecting Next-Gen Autonomous AI Coding',
      '/contacts': 'Support & Contacts | UTIM AI Assistant Community',
      '/referral': 'Referral Program | Earn Credits & Quota Share with UTIM AI'
    };

    const seoDescs = {
      '/home': 'UTIM AI v2.0 is the premier autonomous CLI coding assistant. Featuring Creators Ecosystem, dynamic context compression scaling, and miniagents.',
      '/features': 'Discover UTIM AI capabilities: Creators Ecosystem marketplace, dynamic context scaling, miniagents, custom skills, and MCP server integrations.',
      '/pricing': 'Explore UTIM AI pricing tiers, credit top-ups, rollover quota bank, and BYOK (Bring Your Own Key) unlimited access.',
      '/docs': 'Read official UTIM CLI documentation: installation, command reference, configuration, and security guidelines.',
      '/changelog': 'View complete version release notes, changelog history, and new features introduced in UTIM AI v2.0.'
    };

    if (seoTitles[targetCmd]) {
      document.title = seoTitles[targetCmd];
    }
    const metaDescTag = document.querySelector('meta[name="description"]');
    if (metaDescTag && seoDescs[targetCmd]) {
      metaDescTag.setAttribute('content', seoDescs[targetCmd]);
    }
    
    // Auto-fill terminal history based on active tab
    if (targetCmd === '/features') {
      setHistory([
        { type: 'user', text: '> /features' },
        { type: 'component', name: 'Features' },
        { type: 'empty' }
      ]);
    } else if (targetCmd === '/changelog') {
      setHistory([
        { type: 'user', text: '> /changelog' },
        { type: 'text', text: 'Fetching live release notes from Railway server...', color: '#16c60c' },
        { type: 'component', name: 'Changelog' },
        { type: 'empty' }
      ]);
    } else if (targetCmd === '/about') {
      setHistory([
        { type: 'user', text: '> /about' },
        { type: 'text', text: 'Retrieving architect profiles...', color: '#16c60c' },
        { type: 'component', name: 'About' },
        { type: 'empty' }
      ]);
    } else if (targetCmd === '/pricing') {
      setHistory([
        { type: 'user', text: '> /pricing' },
        { type: 'component', name: 'Pricing' },
        { type: 'empty' }
      ]);
    } else if (targetCmd === '/docs') {
      const isLegal = ['/terms', '/privacy', '/license', '/refund'].includes(path);
      const docName = isLegal ? path.substring(1) : '';
      setHistory([
        { type: 'user', text: isLegal ? `> /docs ${docName}` : '> /docs' },
        { type: 'component', name: 'Docs' },
        { type: 'empty' }
      ]);
    } else if (targetCmd === '/contacts') {
      setHistory([
        { type: 'user', text: '> /contacts' },
        { type: 'text', text: 'Opening secure communication channels & social network matrix...', color: '#16c60c' },
        { type: 'component', name: 'Connect' },
        { type: 'empty' }
      ]);
    } else if (targetCmd === '/referral') {
      setHistory([
        { type: 'user', text: '> /referral' },
        { type: 'text', text: 'Loading referral dashboard...', color: '#00FF66' },
        { type: 'component', name: 'Referral' },
        { type: 'empty' }
      ]);
    } else {
      setHistory(getInitialHistory(user, userProfile, cliVersion));
    }
    
    shouldScrollToBottom.current = false;
  }, [location.pathname, user, userProfile, cliVersion]);

  // Auto-scroll to bottom when history changes, or to top for new pages
  useEffect(() => {
    if (shouldScrollToBottom.current) {
      if (bottomRef.current) {
        bottomRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    } else {
      if (contentRef.current) {
        contentRef.current.scrollTop = 0;
      }
    }
  }, [history]);

  // Focus terminal input only when clicking empty space inside the terminal body specifically
  useEffect(() => {
    const handleTerminalClick = (e) => {
      if (
        inputRef.current &&
        e.target.closest('.term-content') &&
        !e.target.closest('button') &&
        !e.target.closest('input') &&
        !e.target.closest('a') &&
        !e.target.closest('span[style*="cursor: pointer"]') &&
        !e.target.closest('.term-md-card')
      ) {
        inputRef.current.focus();
      }
    };
    document.addEventListener('click', handleTerminalClick);
    return () => document.removeEventListener('click', handleTerminalClick);
  }, []);

  // Fetch latest CLI version from backend server on mount
  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/api/releases`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.length > 0 && data[0].version) {
            const ver = data[0].version;
            setCliVersion(ver);
            setHistory(prev => prev.map(item => {
              if (typeof item.text === 'string' && item.text.startsWith('U Think I Make v')) {
                return { ...item, text: `U Think I Make v${ver}` };
              }
              return item;
            }));
          }
        }
      } catch (err) {
        console.error('Error fetching version from server:', err);
      }
    };
    fetchVersion();
  }, []);

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    
    if (val.startsWith('/')) {
      setShowDropdown(true);
      setSelectedIndex(0);
    } else {
      setShowDropdown(false);
    }
  };

  const filteredCommands = showDropdown
    ? SLASH_COMMANDS.filter(cmd => cmd.cmd.startsWith(input))
    : [];

  const handleChatQuery = async (query) => {
    setLoading(true);
    
    const selectedModel = "openrouter/free";
    
    const userMessage = { role: 'user', content: query };
    const updatedMessages = [...chatMessages, userMessage];
    setChatMessages(updatedMessages);
    
    const SYSTEM_PROMPT = `You are a helpful, professional, and knowledgeable support agent for the UTIM CLI website.
CRITICAL IDENTITY RULE:
- You are the WEBSITE SUPPORT ASSISTANT, NOT the local UTIM CLI agent.
- You CANNOT write code, build apps, edit codebase files, or run terminal commands directly inside this web chat interface.
- If a user asks you to build an app, write code, create software, generate scripts, edit files, or execute commands, you MUST politely inform them:
  "I am the UTIM Web Support Assistant! 🚀 To let UTIM build apps, write code, and run shell commands, you need to run UTIM CLI locally in your terminal."
- Always provide the official installation command:
  \`npm install -g @emend-ai/utim\`
- Explain how to launch it by navigating to their project folder and running \`utim\`.

To answer questions about website docs or features, you MUST use the "read_page_docs" tool.
If the user asks to view pricing or docs, invoke the "navigate_to_page" tool.

Keep your response concise, polite, and under 150 words. Format with clean Markdown. Do NOT generate full app source code.`;

    const tools = [
      {
        type: "function",
        function: {
          name: "read_page_docs",
          description: "Reads the detailed markdown documentation for a specific page or topic on the UTIM CLI website.",
          parameters: {
            type: "object",
            properties: {
              page_name: {
                type: "string",
                enum: ["about", "changelog", "docs", "features", "license", "pricing", "privacy", "refund", "support", "terms"],
                description: "The name of the document or page to read."
              }
            },
            required: ["page_name"]
          }
        }
      },
      {
        type: "function",
        function: {
          name: "navigate_to_page",
          description: "Navigates the user's view on the website to the specified page path.",
          parameters: {
            type: "object",
            properties: {
              page_path: {
                type: "string",
                enum: ["/", "/features", "/about", "/pricing", "/support", "/connect", "/docs", "/referral"],
                description: "The target website URL path to navigate to."
              }
            },
            required: ["page_path"]
          }
        }
      }
    ];

    let currentMessages = [
      { role: 'system', content: SYSTEM_PROMPT },
      ...updatedMessages.map(msg => ({ role: msg.role, content: msg.content }))
    ];

    try {
      const apiUrl = getApiUrl();
      let keepRunning = true;
      let loopCount = 0;
      let finalReply = "";

      while (keepRunning && loopCount < 5) {
        loopCount++;
        const response = await fetch(`${apiUrl}/api/support-chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: selectedModel,
            messages: currentMessages,
            tools: tools
          })
        });

        if (!response.ok) throw new Error('API failure');

        const data = await response.json();
        const assistantMessage = data.message || { role: 'assistant', content: data.reply || "" };

        if (assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0) {
          // Convert this message into a standard text assistant message to avoid API tool validation failures on free models
          const toolCallsText = assistantMessage.tool_calls.map(tc => 
            `<tool_call>\n${tc.function.name}\n<arguments>${tc.function.arguments}</arguments>\n</tool_call>`
          ).join('\n');
          
          currentMessages.push({
            role: 'assistant',
            content: ((assistantMessage.content || '') + '\n' + toolCallsText).trim()
          });

          // Process structured JSON tool calls (OpenAI-compatible models)
          for (const toolCall of assistantMessage.tool_calls) {
            const toolName = toolCall.function.name;
            const args = JSON.parse(toolCall.function.arguments);

            if (toolName === 'read_page_docs') {
              let pageName = args.page_name || args.page || args.page_path || 'docs';
              if (pageName === 'home' || pageName === '/') {
                pageName = 'docs';
              }
              const content = MD_FILES[pageName] || `Document ${pageName} not found.`;
              currentMessages.push({
                role: 'user',
                content: `[Tool result for read_page_docs]: ${content}`
              });
            } else if (toolName === 'navigate_to_page') {
              const pagePath = args.page_path || args.path || args.page || '/';
              navigate(pagePath);
              currentMessages.push({
                role: 'user',
                content: `[Tool result for navigate_to_page]: Successfully navigated user to ${pagePath}`
              });
            }
          }
        } else {
          // Push the assistant message to current messages so the conversation is tracked
          currentMessages.push(assistantMessage);
          // Fallback: parse XML-style tool calls embedded in text content
          // Handles models that output: <tool_call>name\n<arg_key>k</arg_key>\n<arg_value>v</arg_value>\n</tool_call>
          const rawContent = assistantMessage.content || '';
          const toolCallPattern = /<tool_call>([\s\S]*?)<\/tool_call>/g;
          let toolMatch;
          let xmlToolsFound = false;
          let contentWithoutTools = rawContent;

          while ((toolMatch = toolCallPattern.exec(rawContent)) !== null) {
            xmlToolsFound = true;
            const block = toolMatch[1].trim();
            // First line is the tool name
            const lines = block.split('\n');
            const toolName = lines[0].trim();

            // Parse <arg_key> / <arg_value> pairs OR <parameter=name> blocks
            const args = {};
            const argPattern = /<arg_key>([^<]+)<\/arg_key>\s*<arg_value>([\s\S]*?)<\/arg_value>/g;
            let argMatch;
            while ((argMatch = argPattern.exec(block)) !== null) {
              args[argMatch[1].trim()] = argMatch[2].trim();
            }
            // Also handle <parameter=name>value</parameter> style
            const paramPattern = /<parameter=([^>]+)>([\s\S]*?)<\/parameter>/g;
            let paramMatch;
            while ((paramMatch = paramPattern.exec(block)) !== null) {
              args[paramMatch[1].trim()] = paramMatch[2].trim();
            }

            if (toolName === 'read_page_docs') {
              let pageName = args.page_name || args.page || args.page_path || 'docs';
              if (pageName === 'home' || pageName === '/') pageName = 'docs';
              const docContent = MD_FILES[pageName] || `Document ${pageName} not found.`;
              currentMessages.push({ role: 'user', content: `[Tool result for read_page_docs(${pageName})]: ${docContent}` });
            } else if (toolName === 'navigate_to_page') {
              const pagePath = args.page_path || args.path || args.page || '/';
              navigate(pagePath);
              currentMessages.push({ role: 'user', content: `[Tool result for navigate_to_page]: Successfully navigated to ${pagePath}` });
            }

            // Remove the tool call block from the displayed content
            contentWithoutTools = contentWithoutTools.replace(toolMatch[0], '').trim();
          }

          if (!xmlToolsFound) {
            // No tool calls at all — this is the final reply
            finalReply = rawContent;
            keepRunning = false;
          } else {
            // Strip any leading tool-call preamble text so the model responds cleanly
            assistantMessage.content = contentWithoutTools || '';
          }
        }
      }

      setChatMessages(prev => [...prev, { role: 'assistant', content: finalReply }]);
      
      setHistory(prev => [
        ...prev,
        { type: 'markdown', text: finalReply },
        { type: 'empty' }
      ]);
    } catch (error) {
      console.error(error);
      setHistory(prev => [
        ...prev,
        { type: 'text', text: '[!] ERROR: Failed to fetch response. Check connection or try again.', color: '#e74856' },
        { type: 'empty' }
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  };

  const handleKeyDown = (e) => {
    if (showDropdown && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % filteredCommands.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        executeCommand(filteredCommands[selectedIndex]);
      }
    } else {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (input.trim() === '') return;
        
        const query = input.trim();
        shouldScrollToBottom.current = true;
        setHistory(prev => [
          ...prev, 
          { type: 'user', text: `> ${query}` }
        ]);
        setInput('');
        handleChatQuery(query);
      }
    }
  };

  const executeCommand = (cmdObj) => {
    setShowDropdown(false);
    setInput('');
    
    if (cmdObj.cmd === '/login') {
      navigate('/auth');
    } else if (cmdObj.cmd === '/profile') {
      navigate('/profile');
    } else if (cmdObj.cmd === '/clear') {
      setHistory([]);
      setChatMessages([]);
    } else {
      const path = cmdObj.cmd === '/home' ? '/' : cmdObj.cmd;
      if (location.pathname !== path) {
        navigate(path);
      } else {
        shouldScrollToBottom.current = false;
        if (path === '/') {
          setHistory(INITIAL_HISTORY);
        } else if (path === '/features') {
          setHistory([
            { type: 'user', text: '> /features' },
            { type: 'component', name: 'Features' },
            { type: 'empty' }
          ]);
        } else if (path === '/changelog') {
          setHistory([
            { type: 'user', text: '> /changelog' },
            { type: 'text', text: 'Fetching live release notes from Railway server...', color: '#16c60c' },
            { type: 'component', name: 'Changelog' },
            { type: 'empty' }
          ]);
        } else if (path === '/about') {
          setHistory([
            { type: 'user', text: '> /about' },
            { type: 'text', text: 'Retrieving architect profiles...', color: '#16c60c' },
            { type: 'component', name: 'About' },
            { type: 'empty' }
          ]);
        } else if (path === '/referral' || path === '/referrals') {
          setHistory([
            { type: 'user', text: '> /referral' },
            { type: 'text', text: 'Loading referral dashboard...', color: '#00FF66' },
            { type: 'component', name: 'Referral' },
            { type: 'empty' }
          ]);
        } else if (path === '/pricing') {
          setHistory([
            { type: 'user', text: '> /pricing' },
            { type: 'component', name: 'Pricing' },
            { type: 'empty' }
          ]);
        } else if (path === '/docs') {
          setHistory([
            { type: 'user', text: '> /docs' },
            { type: 'component', name: 'Docs' },
            { type: 'empty' }
          ]);
        } else if (path === '/contacts') {
          setHistory([
            { type: 'user', text: '> /contacts' },
            { type: 'text', text: 'Opening secure communication channels...', color: '#16c60c' },
            { type: 'component', name: 'Connect' },
            { type: 'empty' }
          ]);
        } else if (path === '/connect') {
          setHistory([
            { type: 'user', text: '> /connect' },
            { type: 'text', text: 'Establishing neural network link...', color: '#16c60c' },
            { type: 'component', name: 'Connect' },
            { type: 'empty' }
          ]);
        }
      }
    }
  };

  return (
    <div className="term-wrapper">
      <div className="term-window">
        {/* Modern Windows Terminal Tab Bar acting as Navbar */}
        <div className="term-titlebar">
          <div className={`term-tab ${activeTab === '/home' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/home'})}>
            <span className="term-tab-icon" style={{color: '#3b78ff'}}>&gt;_</span>
            <span className="term-tab-title">Home</span>
          </div>
          <div className={`term-tab ${activeTab === '/features' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/features'})}>
            <span className="term-tab-icon" style={{color: '#f9f1a5'}}>#</span>
            <span className="term-tab-title">Features</span>
          </div>
          <div className={`term-tab ${activeTab === '/about' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/about'})}>
            <span className="term-tab-icon" style={{color: '#B266FF'}}>@</span>
            <span className="term-tab-title">About</span>
          </div>
          <div className={`term-tab ${activeTab === '/pricing' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/pricing'})}>
            <span className="term-tab-icon" style={{color: '#16c60c'}}>$</span>
            <span className="term-tab-title">Pricing</span>
          </div>
          <div className={`term-tab ${activeTab === '/docs' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/docs'})}>
            <span className="term-tab-icon" style={{color: '#5bc0de'}}>?</span>
            <span className="term-tab-title">Docs</span>
          </div>
          <div className={`term-tab ${activeTab === '/changelog' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/changelog'})}>
            <span className="term-tab-icon" style={{color: '#E5FF00'}}>↻</span>
            <span className="term-tab-title">Changelog</span>
          </div>
          <div className={`term-tab ${activeTab === '/contacts' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/contacts'})}>
            <span className="term-tab-icon" style={{color: '#FF8C00'}}>~</span>
            <span className="term-tab-title">Contacts</span>
          </div>
          <div className={`term-tab ${activeTab === '/referral' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/referral'})}>
            <span className="term-tab-icon" style={{color: '#00FF66'}}>%</span>
            <span className="term-tab-title">Referrals</span>
          </div>
          {isAuthenticated ? (
            <div className={`term-tab ${activeTab === '/profile' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/profile'})}>
              <span className="term-tab-icon" style={{color: '#16c60c'}}>$</span>
              <span className="term-tab-title">Profile</span>
            </div>
          ) : (
            <div className={`term-tab ${activeTab === '/login' ? 'active' : ''}`} onClick={() => executeCommand({cmd: '/login'})}>
              <span className="term-tab-icon" style={{color: '#e74856'}}>*</span>
              <span className="term-tab-title">Sign In</span>
            </div>
          )}
          <div className="term-tab-add">+</div>
          <div className="term-tab-chevron">v</div>
          <div className="term-window-controls">
            <div className="term-ctrl">_</div>
            <div className="term-ctrl">□</div>
            <div className="term-ctrl close">×</div>
          </div>
        </div>

        {/* Web Support Agent Disclaimer Banner */}
        {showSupportBanner && (
          <div className="term-support-disclaimer">
            <div className="ts-badge">
              <span className="ts-pulse">●</span> WEB SUPPORT ASSISTANT
            </div>
            <div className="ts-text">
              This chat is our <strong>Web Support Bot</strong>. To build apps, edit code, and run commands, install the UTIM CLI on your local computer.
            </div>
            <div className="ts-npm-pill" onClick={handleCopyNpmBanner} title="Click to copy npm install command">
              <code>npm install -g @emend-ai/utim</code>
              <span className="ts-copy-btn-label">
                {npmBannerCopied ? '✓ Copied!' : 'Copy'}
              </span>
            </div>
            <button 
              className="ts-close-btn" 
              onClick={handleCloseSupportBanner}
              title="Close banner"
              aria-label="Close banner"
            >
              ✕
            </button>
          </div>
        )}

        {/* July Special Promotional Banner */}
        <PromotionalBanner onOpenModal={() => setIsPromoModalOpen(true)} />

        {/* Promotional Offers Popup Modal */}
        <PromoModal isOpen={isPromoModalOpen} onClose={() => setIsPromoModalOpen(false)} />

        <div className="term-content" ref={contentRef}>
          {history.map((item, idx) => {
            if (item.type === 'empty') return <div key={idx} className="term-line">&nbsp;</div>;
            if (item.type === 'banner') {
              const userEmail = user?.email || 'local@utim.dev';
              const rawPlan = userProfile?.plan || 'free';
              const planDisplayName = rawPlan === 'free' ? 'Community' : (rawPlan.charAt(0).toUpperCase() + rawPlan.slice(1));
              const userType = `UTIM ${planDisplayName}`;
              return <div key={idx} className="term-line" style={{ color: '#888' }}>{userEmail}  •  {userType}</div>;
            }
            if (item.type === 'command') return <div key={idx} className="term-line term-yellow">{item.text}</div>;
            if (item.type === 'user') return <div key={idx} className="term-line term-cyan">{item.text}</div>;
            if (item.type === 'ascii') return <pre key={idx} className="term-ascii">{item.text}</pre>;
            if (item.type === 'box') return (
              <div key={idx} className="term-box">
                {item.text.map((line, i) => <div key={i}>{line}</div>)}
              </div>
            );
            if (item.type === 'codeblock') return (
              <CodeBlockContainer key={idx} code={item.code} lang={item.lang} />
            );
            if (item.type === 'markdown') return (
              <div key={idx} className="term-markdown">
                <ReactMarkdown
                  components={{
                    code({node, inline, className, children, ...props}) {
                      const match = /language-(\w+)/.exec(className || '')
                      return !inline && match ? (
                        <CodeBlockContainer code={String(children).replace(/\n$/, '')} lang={match[1]} />
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      )
                    }
                  }}
                >
                  {item.text}
                </ReactMarkdown>
              </div>
            );
            if (item.type === 'empty') return <div key={idx} className="term-line">&nbsp;</div>;
            if (item.type === 'component') {
              if (item.name === 'Features') return <InlineFeatures key={idx} />;
              if (item.name === 'Pricing') return <InlinePricing key={idx} />;
              if (item.name === 'About') return <InlineAbout key={idx} />;
              if (item.name === 'Connect') return <InlineConnect key={idx} />;
              if (item.name === 'Changelog') return <InlineChangelog key={idx} />;
              if (item.name === 'Referral') return <InlineReferral key={idx} />;
              if (item.name === 'Docs') {
                const articleId = ['/terms', '/privacy', '/license', '/refund'].includes(location.pathname) 
                  ? location.pathname.substring(1) 
                  : 'overview';
                return <InlineDocs key={idx} initialArticle={articleId} />;
              }
              if (item.name === 'Highlights') return <InlineHighlights key={idx} />;
              return null;
            }
            return <div key={idx} className="term-line" style={{ color: item.color }}>{item.text}</div>;
          })}
          
          {loading && (
            <div className="term-line term-loading">
              <span className="term-dot">.</span>
              <span className="term-dot">.</span>
              <span className="term-dot">.</span>
            </div>
          )}
          
          <div ref={bottomRef} />
        </div>

        {/* Input Area and Dropdown */}
        <div className="term-input-area">
          {/* Dropdown Menu */}
          {showDropdown && filteredCommands.length > 0 && (
            <div className="term-dropdown">
              {filteredCommands.map((cmd, idx) => (
                <div 
                  key={idx} 
                  className={`term-dropdown-item ${idx === selectedIndex ? 'active' : ''}`}
                  onClick={() => executeCommand(cmd)}
                >
                  <span className="td-cmd">{cmd.cmd}</span>
                  <span className="td-desc">{cmd.desc}</span>
                </div>
              ))}
            </div>
          )}

          {/* Top Status Bar */}
          <div className="term-status-row">
            <div className="ts-left">
              <span className="ts-gray">Ask UTIM support chat about your queries or connect with us.</span>
            </div>
            <div className="ts-right ts-gray">
              Tip: Copy the last response with /copy
            </div>
          </div>

          {/* Termux Mobile Touch Extra Keys Bar */}
          <div className="termux-keys-bar">
            <button className="tk-btn" onClick={() => executeCommand({cmd: '/clear'})}>ESC</button>
            <button className="tk-btn tk-accent" onClick={() => { setInput('/'); setShowDropdown(true); }}>/</button>
            <button className="tk-btn" onClick={() => setInput(prev => prev + '-')}>-</button>
            <button className="tk-btn" onClick={() => setInput(prev => prev + '~')}>~</button>
            <button className="tk-btn" onClick={() => executeCommand({cmd: '/features'})}>Cap</button>
            <button className="tk-btn" onClick={() => executeCommand({cmd: '/pricing'})}>Plan</button>
            <button className="tk-btn" onClick={() => executeCommand({cmd: '/docs'})}>Docs</button>
            <button className="tk-btn tk-enter" onClick={() => {
              if (showDropdown) {
                executeCommand(SLASH_COMMANDS[selectedIndex]);
              } else if (input.trim()) {
                const query = input.trim();
                shouldScrollToBottom.current = true;
                setHistory(prev => [...prev, { type: 'user', text: `> ${query}` }]);
                setInput('');
                handleChatQuery(query);
              }
            }}>▶</button>
          </div>

          {/* Interactive Prompt */}
          <div className="term-prompt-row">
            <span className="term-prompt-arrow">{isAndroid ? '~ $' : '▶'}</span>
            <input 
              ref={inputRef}
              type="text" 
              className="term-input" 
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              spellCheck="false"
              autoComplete="off"
              disabled={loading}
              placeholder={loading ? "Thinking..." : 'Type "/" for menu'}
            />
          </div>

          {/* Bottom Status Bar */}
          <div className="term-status-bottom">
            <div className="tsb-left">
              <div className="ts-gray">workspace (/directory)</div>
              <div>C:\projects\utim</div>
            </div>
            <div className="tsb-right">
              <div className="ts-gray">state | sandbox</div>
              <div><span className="ts-red">state: active</span> | <span className="ts-red">no sandbox</span></div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default PowershellUI;
