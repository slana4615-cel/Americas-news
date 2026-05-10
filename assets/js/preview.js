/**
 * 新闻条目预览功能
 * 桌面端：悬停时显示预览
 * 移动端：点击时显示预览
 */

class ArticlePreview {
    constructor() {
        this.activePreview = null;
        this.isMobile = window.innerWidth <= 768;
        this.previewTimeout = null;
        this.overlay = null;
        
        this.init();
    }
    
    init() {
        this.createOverlay();
        this.attachEventListeners();
        this.handleResize();
    }
    
    createOverlay() {
        // 创建移动端遮罩层。
        this.overlay = document.createElement('div');
        this.overlay.className = 'preview-overlay';
        this.overlay.addEventListener('click', () => this.hideActivePreview());
        document.body.appendChild(this.overlay);
    }
    
    attachEventListeners() {
        const cards = document.querySelectorAll('.card');
        
        cards.forEach(card => {
            const preview = card.querySelector('.card-preview');
            if (!preview) return;
            
            if (this.isMobile) {
                // 移动端：点击显示预览。
                card.addEventListener('click', (e) => this.handleMobileClick(e, card, preview));
            } else {
                // 桌面端：悬停预览，点击打开原文。
                card.addEventListener('mouseenter', (e) => {
                    // 点击标题链接时不显示预览。
                    if (e.target.tagName === 'A') return;
                    this.handleDesktopHover(card, preview);
                });
                card.addEventListener('mouseleave', (e) => this.handleDesktopLeave(card, preview));
                card.addEventListener('click', (e) => this.handleDesktopClick(e, card));
            }
        });
        
        // 按 ESC 关闭预览。
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideActivePreview();
            }
        });
    }
    
    handleMobileClick(event, card, preview) {
        // 点击链接时直接打开原文。
        if (event.target.tagName === 'A' || event.target.closest('a')) {
            return; // 保留默认链接行为。
        }
        
        event.preventDefault();
        
        // 如果预览已经显示，则关闭。
        if (preview.classList.contains('show')) {
            this.hidePreview(preview);
            return;
        }
        
        // 关闭其他预览。
        this.hideActivePreview();
        
        // 显示预览。
        this.showPreview(preview);
        this.activePreview = preview;
    }
    
    handleDesktopHover(card, preview) {
        // 延迟显示，减少闪烁。
        this.previewTimeout = setTimeout(() => {
            this.hideActivePreview();
            this.showPreview(preview);
            this.activePreview = preview;
            
            // 调整预览位置。
            this.adjustPreviewPosition(card, preview);
        }, 800);
    }
    
    handleDesktopLeave(card, preview) {
        // 清除悬停延迟。
        if (this.previewTimeout) {
            clearTimeout(this.previewTimeout);
            this.previewTimeout = null;
        }
        
        // 预览显示时稍作延迟后关闭。
        setTimeout(() => {
            if (this.activePreview === preview && !this.isHoveringPreview(preview)) {
                this.hidePreview(preview);
                this.activePreview = null;
            }
        }, 200);
    }
    
    handleDesktopClick(event, card) {
        // 点击链接时保留默认行为。
        if (event.target.tagName === 'A' || event.target.closest('a')) {
            return;
        }
        
        // 点击整张卡片打开原文。
        const articleLink = card.querySelector('.card-title a');
        if (articleLink) {
            // 在新标签页打开原文。
            window.open(articleLink.href, '_blank');
        }
    }
    
    showPreview(preview) {
        // 将预览移动到 body 下，避免 z-index 冲突。
        if (preview.parentNode !== document.body) {
            document.body.appendChild(preview);
        }
        
        // 控制作者信息显示。
        this.updateAuthorDisplay(preview);
        
        preview.style.display = 'block';
        
        // 触发布局计算。
        preview.offsetHeight;
        
        preview.classList.add('show');
        
        if (this.isMobile) {
            this.overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    }
    
    updateAuthorDisplay(preview) {
        const authorElement = preview.querySelector('.preview-author');
        if (authorElement) {
            const authorInfo = authorElement.textContent.trim();
            
            if (authorInfo && authorInfo !== '') {
                // 有作者信息时显示。
                authorElement.style.display = 'inline';
                authorElement.textContent = `by ${authorInfo}`;
            } else {
                // 无作者信息时隐藏。
                authorElement.style.display = 'none';
            }
        }
    }
    
    hidePreview(preview) {
        preview.classList.remove('show');
        
        setTimeout(() => {
            preview.style.display = 'none';
        }, 300);
        
        if (this.isMobile) {
            this.overlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    }
    
    hideActivePreview() {
        if (this.activePreview) {
            this.hidePreview(this.activePreview);
            this.activePreview = null;
        }
    }
    
    adjustPreviewPosition(card, preview) {
        if (this.isMobile) return;
        
        const cardRect = card.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // 估算预览尺寸。
        const previewWidth = 400; // 来自 max-width
        const previewHeight = preview.scrollHeight || 300;
        
        // 调整横向位置。
        let left = cardRect.left;
        if (left + previewWidth > viewportWidth - 20) {
            left = viewportWidth - previewWidth - 20;
        }
        if (left < 20) {
            left = 20;
        }
        
        // 调整纵向位置。
        let top = cardRect.bottom + 8;
        if (top + previewHeight > viewportHeight - 20) {
            top = cardRect.top - previewHeight - 8;
            if (top < 20) {
                top = 20;
            }
        }
        
        // 使用 position: fixed 定位。
        preview.style.left = left + 'px';
        preview.style.top = top + 'px';
        preview.style.right = 'auto';
        preview.style.bottom = 'auto';
        preview.style.marginTop = '0';
        preview.style.marginBottom = '0';
    }
    
    isHoveringPreview(preview, event = null) {
        // 未提供事件对象时，检查元素悬停状态。
        if (!event) {
            return preview.matches(':hover');
        }
        
        const previewRect = preview.getBoundingClientRect();
        const mouseX = event.clientX;
        const mouseY = event.clientY;
        
        return mouseX >= previewRect.left && mouseX <= previewRect.right &&
               mouseY >= previewRect.top && mouseY <= previewRect.bottom;
    }
    
    handleResize() {
        window.addEventListener('resize', () => {
            const wasMobile = this.isMobile;
            this.isMobile = window.innerWidth <= 768;
            
            // 移动端和桌面端切换时重设事件监听。
            if (wasMobile !== this.isMobile) {
                this.hideActivePreview();
                this.removeEventListeners();
                this.attachEventListeners();
            }
        });
    }
    
    removeEventListeners() {
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            card.replaceWith(card.cloneNode(true));
        });
    }
}

// 供 HTML 调用的全局预览关闭函数。
function hidePreview(event, cardId) {
    event.preventDefault();
    event.stopPropagation();
    
    const preview = document.getElementById(`preview-${cardId}`);
    if (preview && window.articlePreview) {
        window.articlePreview.hidePreview(preview);
        window.articlePreview.activePreview = null;
    }
}

// DOM 加载完成后初始化。
document.addEventListener('DOMContentLoaded', () => {
    window.articlePreview = new ArticlePreview();
});

// 页面显示时也初始化，兼容浏览器返回。
window.addEventListener('pageshow', () => {
    if (!window.articlePreview) {
        window.articlePreview = new ArticlePreview();
    }
});

/**
 * 标签筛选功能
 * 根据标签筛选新闻卡片。
 */
class TagFilter {
    constructor() {
        this.activeTag = 'all';
        this.cards = [];
        this.buttons = [];
        this.tagCounts = {};
        
        this.init();
    }
    
    init() {
        this.cards = Array.from(document.querySelectorAll('.card'));
        this.buttons = Array.from(document.querySelectorAll('.tag-filter-btn'));
        this.countTagsInCards();
        this.updateTagCounts();
        this.attachEventListeners();
    }
    
    countTagsInCards() {
        this.tagCounts = { 'all': this.cards.length };
        
        this.cards.forEach(card => {
            const tagsElement = card.querySelector('.preview-tags');
            if (tagsElement) {
                const tags = tagsElement.textContent.split(',').map(tag => tag.trim());
                tags.forEach(tag => {
                    if (tag && tag !== '') {
                        this.tagCounts[tag] = (this.tagCounts[tag] || 0) + 1;
                    }
                });
            }
        });
    }
    
    updateTagCounts() {
        this.buttons.forEach(button => {
            const tag = button.dataset.tag;
            const count = this.tagCounts[tag] || 0;
            
            if (tag === 'all') {
                button.textContent = `全部 (${this.tagCounts['all']})`;
            } else if (count > 0) {
                button.textContent = `${tag} (${count})`;
                button.style.display = 'inline-block';
            } else {
                button.style.display = 'none';
            }
        });
    }
    
    attachEventListeners() {
        this.buttons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const tag = button.dataset.tag;
                this.filterByTag(tag);
                this.updateActiveButton(button);
            });
        });
    }
    
    filterByTag(tag) {
        this.activeTag = tag;
        let visibleCount = 0;
        
        this.cards.forEach((card) => {
            const shouldShow = this.shouldShowCard(card, tag);
            
            if (shouldShow) {
                card.style.display = 'block';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
                visibleCount++;
            } else {
                card.style.display = 'none';
                card.style.opacity = '0';
                card.style.transform = 'translateY(-10px)';
            }
        });
        
        // 立即更新分区标题。
        this.updateSectionHeaders();
        
        // 展示筛选反馈。
        this.showFilterResults(tag, visibleCount);
        
        // 更新筛选状态。
        this.updateFilterStatus(tag, visibleCount);
    }
    
    updateSectionHeaders() {
        // 获取所有分区标题。
        const headers = document.querySelectorAll('h2');
        
        headers.forEach(header => {
            // 统计标题下方的新闻卡片。
            let visibleCardsInSection = 0;
            let nextElement = header.nextElementSibling;
            
            // 检查当前标题到下一个 h2 之间的卡片。
            while (nextElement && nextElement.tagName !== 'H2') {
                if (nextElement.classList.contains('card')) {
                    const cardStyle = window.getComputedStyle(nextElement);
                    if (cardStyle.display !== 'none' && nextElement.style.opacity !== '0') {
                        visibleCardsInSection++;
                    }
                }
                nextElement = nextElement.nextElementSibling;
            }
            
            // 没有可显示条目时隐藏标题。
            if (visibleCardsInSection === 0) {
                header.style.display = 'none';
            } else {
                header.style.display = 'block';
            }
        });
    }
    
    
    shouldShowCard(card, tag) {
        if (tag === 'all') return true;
        
        const tagsElement = card.querySelector('.preview-tags');
        if (!tagsElement) return false;
        
        const cardTags = tagsElement.textContent.split(',').map(t => t.trim());
        return cardTags.includes(tag);
    }
    
    updateActiveButton(activeButton) {
        this.buttons.forEach(button => {
            button.classList.remove('active');
        });
        activeButton.classList.add('active');
    }
    
    showFilterResults(tag, count) {
        // 删除已有结果提示。
        const existingResult = document.querySelector('.filter-result');
        if (existingResult) {
            existingResult.remove();
        }
        
        // 显示筛选结果。
        const resultElement = document.createElement('div');
        resultElement.className = 'filter-result';
        resultElement.style.cssText = `
            margin: 10px 0;
            padding: 8px 12px;
            background: #e7f3ff;
            border: 1px solid #b6e3ff;
            border-radius: 6px;
            font-size: 14px;
            color: #0969da;
            text-align: center;
        `;
        
        if (tag === 'all') {
            resultElement.textContent = `正在显示全部条目（${count}）`;
        } else {
            resultElement.textContent = `正在按「${tag}」筛选（${count}）`;
        }
        
        // 插入到标签筛选器之后。
        const filterContainer = document.querySelector('.tag-filter-container');
        if (filterContainer) {
            filterContainer.insertAdjacentElement('afterend', resultElement);
            
            // 3 秒后自动移除。
            setTimeout(() => {
                if (resultElement.parentNode) {
                    resultElement.remove();
                }
            }, 3000);
        }
    }
    
    updateFilterStatus(tag, visibleCount) {
        const filterStatus = document.getElementById('filterStatus');
        const filterStatusText = document.getElementById('filterStatusText');
        
        if (tag === 'all') {
            filterStatus.style.display = 'none';
        } else {
            filterStatus.style.display = 'flex';
            filterStatusText.textContent = `正在按「${tag}」筛选（${visibleCount}）`;
        }
    }
}

// DOM 加载完成后初始化标签筛选。
document.addEventListener('DOMContentLoaded', () => {
    window.tagFilter = new TagFilter();
});

// 页面显示时也初始化，兼容浏览器返回。
window.addEventListener('pageshow', () => {
    if (!window.tagFilter) {
        window.tagFilter = new TagFilter();
    }
});

/**
 * 清除标签筛选，恢复全部显示。
 */
function clearTagFilter() {
    if (window.tagFilter) {
        // 找到“全部”按钮并模拟点击。
        const allButton = document.querySelector('.tag-filter-btn[data-tag="all"]');
        if (allButton) {
            window.tagFilter.filterByTag('all');
            window.tagFilter.updateActiveButton(allButton);
        }
    }
}

/**
 * 标签筛选器折叠功能。
 */
function toggleTagFilter() {
    const filterBar = document.getElementById('tagFilterBar');
    const toggleBtn = document.querySelector('.filter-toggle-btn');
    
    if (filterBar.classList.contains('collapsed')) {
        // 展开。
        filterBar.classList.remove('collapsed');
        filterBar.classList.add('expanded');
        toggleBtn.classList.add('expanded');
    } else {
        // 折叠。
        filterBar.classList.remove('expanded');
        filterBar.classList.add('collapsed');
        toggleBtn.classList.remove('expanded');
    }
}

/**
 * 深色模式功能
 * 提供系统设置检测、用户设置持久化和主题切换。
 */
class ThemeManager {
    constructor() {
        this.themeKey = 'tech-news-theme';
        this.prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
        this.hideTimeout = null;
        this.isHovered = false;
        this.lastScrollY = window.scrollY;
        
        this.init();
    }
    
    init() {
        // 创建浮动按钮。
        this.createFloatingButton();
        
        // 应用已保存主题或系统设置。
        this.applyInitialTheme();
        
        // 为主题切换按钮添加事件监听。
        this.attachEventListeners();
        
        // 监听系统主题变化。
        this.watchSystemTheme();
        
        // 设置自动显示和隐藏。
        this.setupAutoHide();
    }
    
    applyInitialTheme() {
        const savedTheme = localStorage.getItem(this.themeKey);
        
        if (savedTheme) {
            // 使用已保存主题。
            this.setTheme(savedTheme);
        } else {
            // 跟随系统设置。
            const systemTheme = this.prefersDark.matches ? 'dark' : 'light';
            this.setTheme(systemTheme, false); // 不写入 localStorage
        }
    }
    
    attachEventListeners() {
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    }
    
    createFloatingButton() {
        // 删除已有按钮。
        const existingButton = document.getElementById('theme-toggle');
        if (existingButton) {
            existingButton.remove();
        }
        
        // 创建浮动按钮。
        const button = document.createElement('button');
        button.id = 'theme-toggle';
        button.title = '切换深色模式';
        button.setAttribute('aria-label', '切换主题');
        
        const icon = document.createElement('span');
        icon.id = 'theme-icon';
        icon.textContent = '🌙';
        
        const text = document.createElement('span');
        text.id = 'theme-text';
        text.textContent = '深色模式';
        
        button.appendChild(icon);
        button.appendChild(text);
        
        // 添加悬停事件。
        button.addEventListener('mouseenter', () => {
            this.isHovered = true;
            this.showButton();
        });
        
        button.addEventListener('mouseleave', () => {
            this.isHovered = false;
            this.scheduleHide();
        });
        
        // 添加到 body。
        document.body.appendChild(button);
    }
    
    watchSystemTheme() {
        // 系统主题变化时，仅在用户未显式设置时跟随。
        this.prefersDark.addEventListener('change', (e) => {
            const savedTheme = localStorage.getItem(this.themeKey);
            if (!savedTheme) {
                // 仅在没有用户设置时跟随系统。
                const systemTheme = e.matches ? 'dark' : 'light';
                this.setTheme(systemTheme, false);
            }
        });
    }
    
    getCurrentTheme() {
        return document.documentElement.getAttribute('data-theme') || 
               (this.prefersDark.matches ? 'dark' : 'light');
    }
    
    setTheme(theme, saveToStorage = true) {
        // 设置 HTML 的 data-theme 属性。
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        
        // 更新按钮文字和图标。
        this.updateThemeButton(theme);
        
        // 写入 localStorage；跟随系统设置时不保存。
        if (saveToStorage) {
            localStorage.setItem(this.themeKey, theme);
        }
        
        // 添加平滑切换动画。
        this.addTransitionClass();
    }
    
    toggleTheme() {
        const currentTheme = this.getCurrentTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        this.setTheme(newTheme);
        
        // 显示切换反馈。
        this.showThemeChangeNotification(newTheme);
    }
    
    updateThemeButton(theme) {
        const themeIcon = document.getElementById('theme-icon');
        const themeText = document.getElementById('theme-text');
        
        if (themeIcon && themeText) {
            if (theme === 'dark') {
                themeIcon.textContent = '☀️';
                themeText.textContent = '浅色模式';
            } else {
                themeIcon.textContent = '🌙';
                themeText.textContent = '深色模式';
            }
        }
    }
    
    addTransitionClass() {
        // 临时添加切换动画类。
        document.documentElement.classList.add('theme-transition');
        
        setTimeout(() => {
            document.documentElement.classList.remove('theme-transition');
        }, 300);
    }
    
    showThemeChangeNotification(theme) {
        // 显示切换通知。
        const notification = document.createElement('div');
        notification.className = 'theme-notification';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--card-bg);
            color: var(--text-color);
            border: 1px solid var(--border-color);
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            z-index: 10000;
            opacity: 0;
            transform: translateY(-20px);
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px var(--shadow-medium);
        `;
        
        const themeName = theme === 'dark' ? '深色模式' : '浅色模式';
        notification.textContent = `已切换到${themeName}`;
        
        document.body.appendChild(notification);
        
        // 显示动画。
        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        });
        
        // 2 秒后移除。
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-20px)';
            
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }, 2000);
    }
    
    setupAutoHide() {
        // 初始显示，3 秒后自动隐藏。
        this.showButton();
        this.scheduleHide(3000);
        
        // 监听滚动事件。
        let scrollTimeout;
        window.addEventListener('scroll', () => {
            // 滚动时显示。
            this.showButton();
            
            // 防抖检测滚动停止。
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                if (!this.isHovered) {
                    this.scheduleHide(1500); // 滚动停止 1.5 秒后隐藏
                }
            }, 150);
        });
        
        // 鼠标移至屏幕边缘附近时显示。
        document.addEventListener('mousemove', (e) => {
            const rightEdgeThreshold = window.innerWidth - 150; // 右侧 150px
            const topEdgeThreshold = 150; // 顶部 150px
            
            if (e.clientX > rightEdgeThreshold && e.clientY < topEdgeThreshold) {
                this.showButton();
                this.scheduleHide(2000); // 2 秒后隐藏
            }
        });
    }
    
    showButton() {
        const button = document.getElementById('theme-toggle');
        if (button) {
            button.style.opacity = '0.8';
            button.style.visibility = 'visible';
            button.style.pointerEvents = 'auto';
        }
        
        // 清除已有定时器。
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
    }
    
    hideButton() {
        const button = document.getElementById('theme-toggle');
        if (button && !this.isHovered) {
            button.style.opacity = '0';
            button.style.pointerEvents = 'none';
            
            // 动画结束后完全隐藏。
            setTimeout(() => {
                if (button.style.opacity === '0') {
                    button.style.visibility = 'hidden';
                }
            }, 300);
        }
    }
    
    scheduleHide(delay = 2000) {
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }
        
        this.hideTimeout = setTimeout(() => {
            if (!this.isHovered) {
                this.hideButton();
            }
        }, delay);
    }
}

// DOM 加载完成后初始化主题管理器。
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});

// 页面显示时也初始化，兼容浏览器返回。
window.addEventListener('pageshow', () => {
    if (!window.themeManager) {
        window.themeManager = new ThemeManager();
    }
});
