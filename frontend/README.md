# Frontend - Computer Vision Quality Control

Modern, responsive web interface for automated product quality inspection using computer vision (YOLO11-seg).

## 📁 Directory Structure

```
frontend/
├── index.html                 # Main application page
├── css/
│   ├── style.css             # Core styling (1000+ lines)
│   └── responsive.css        # Mobile/tablet responsive design
├── js/
│   ├── app.js                # Application entry point & state management
│   ├── api.js                # Backend API client (HTTP wrapper)
│   ├── ui.js                 # UI components & event handlers
│   └── utils.js              # Utility functions (storage, formatting, etc.)
├── pages/                    # (Optional) Individual page templates
├── assets/                   # Images, icons, placeholders
└── README.md                 # This file
```

## 🚀 Quick Start

### Prerequisites
- Backend API running on `http://localhost:8000`
- Modern browser (Chrome, Firefox, Safari, Edge)

### Installation & Running

1. **Static Server Setup (Option A - Serve from Backend)**
   - Copy entire `frontend` folder to `backend/static/` on your server
   - Access at: `http://localhost:8000/` (or configure backend to serve)

2. **Development Server (Option B - Separate Server)**
   ```bash
   # Using Python
   python -m http.server 3000 --directory frontend

   # Using Node.js http-server
   npx http-server frontend -p 3000

   # Using Live Server in VS Code
   # Right-click index.html > "Open with Live Server"
   ```
   - Access at: `http://localhost:3000`

### Configuration

Edit `index.html` or check `js/api.js` to configure backend URL:
```javascript
const API_BASE = 'http://localhost:8000';
```

## 📋 Features

### 1. **Dashboard**
- Real-time statistics (total, passed, flagged, rejected)
- Recent inspections table
- Quick navigation

### 2. **Upload & Inspect**
- Drag-and-drop or click-to-upload image
- Adjustable confidence threshold (0.0-1.0)
- Frame skip rate configuration for videos
- Real-time processing feedback

### 3. **Results Display**
- Annotated image with bounding boxes & segmentation masks
- Detailed defect predictions (confidence, area, position, severity)
- Inspection verdict (PASS/FLAG/REJECT)
- Automatic VQA answers to common questions
- Inspection report with recommendations

### 4. **History**
- Paginated inspection history (10 items/page)
- Filter by verdict (PASS, FLAG, REJECT)
- View detailed inspection data
- Delete inspection records
- Search & sorting ready

### 5. **Settings**
- Adjust confidence threshold
- Set frame skip rate
- Toggle label visibility
- Dark/Light theme toggle
- Keyboard shortcuts reference
- Settings persistence (LocalStorage)

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + U` | Go to Upload page |
| `Ctrl + H` | Go to History page |
| `Ctrl + D` | Go to Dashboard |
| `Ctrl + T` | Toggle Dark/Light theme |

## 🎨 Styling & Theming

### Color Scheme
- **Primary**: `#2563eb` (Blue)
- **Success**: `#10b981` (Green - PASS)
- **Warning**: `#f59e0b` (Amber - FLAG)
- **Danger**: `#ef4444` (Red - REJECT)
- **Info**: `#0ea5e9` (Sky Blue - VQA)

### Responsive Design
- **Desktop** (≥1200px): Full layout
- **Tablet** (768px-1199px): Optimized columns
- **Mobile** (<768px): Single column, optimized touch targets
- **Small Mobile** (<375px): Extra-compact layout

### Dark Mode
- User can toggle theme anytime
- Settings saved to LocalStorage
- CSS uses `data-bs-theme="dark"` attribute
- Bootstrap 5 native dark mode support

## 🔌 API Integration

### Key Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /inspect` | POST | Full pipeline inspection |
| `POST /segment` | POST | Segmentation only |
| `POST /detect` | POST | Detection only |
| `POST /vqa` | POST | Ask questions about image |
| `POST /caption` | POST | Generate image caption |
| `GET /logs` | GET | Get inspection history |
| `POST /process_video` | POST | Process video |
| `/` | GET | Health check |

See `js/api.js` for full documentation.

## 💾 Data Persistence

### LocalStorage Keys
- `settings` - User preferences (confidence, skipRate, showLabels, darkMode)
- `theme` - Current theme (light/dark)

### Session Storage
- `currentInspection` - Current inspection data
- `currentPage` - Last viewed page

## 🛠️ Development Guide

### Adding New Features

1. **New Page**
   - Add page div in `index.html`: `<div data-page="new-page">`
   - Add navigation link: `<a data-nav="new-page">`
   - Implement in `ui.js`: `navigateToPage('new-page')`

2. **New API Endpoint**
   - Add method in `APIClient` class in `js/api.js`
   - Call from UI components in `js/ui.js`

3. **New UI Component**
   - Create component class in `js/ui.js`
   - Add event listeners in `init()` method
   - Style in `css/style.css`

### Code Organization

- **api.js**: All backend communication
- **utils.js**: Reusable utilities (formatting, storage, validation)
- **ui.js**: UI logic, event handlers, data display
- **app.js**: Global state, initialization, keyboard shortcuts
- **style.css**: All styling rules
- **responsive.css**: Media queries & responsive adjustments

## 📱 Mobile Optimization

- Touch-friendly button sizes (≥44px)
- Vertical scrolling priority (no horizontal scroll)
- Large tap targets (min 48x48px)
- Simplified table layout on mobile (stacked rows)
- Optimized modal sizes for small screens
- Readable font sizes (16px minimum on mobile)

## ♿ Accessibility

- ARIA labels on all interactive elements
- Keyboard navigation support
- Color contrast ratio > 4.5:1
- Focus indicators on all buttons/inputs
- Alt text on all images
- Semantic HTML structure
- Screen reader friendly

## 🐛 Browser Support

- **Chrome/Edge**: ✅ Latest 2 versions
- **Firefox**: ✅ Latest 2 versions
- **Safari**: ✅ Latest 2 versions
- **Mobile Safari** (iOS): ✅ iOS 12+
- **Chrome Mobile**: ✅ Latest version

## 📊 Performance

- **Initial Load**: < 2s
- **Image Upload**: < 5s (depends on image size & backend)
- **History Pagination**: < 1s
- **Theme Toggle**: < 200ms

### Optimization Tips
- Lazy-load history data (use pagination)
- Cache API responses (10s TTL)
- Minimize CSS/JS in production
- Compress images (max 5MB)

## 🔐 Security

- No sensitive data stored locally
- HTTPS recommended in production
- CORS must be configured on backend
- Input validation on file uploads
- XSS prevention via textContent (not innerHTML when unsafe)

## 📝 Logging & Debugging

### Enable Debug Mode
```javascript
// In browser console
localStorage.setItem('debug', 'true');
location.reload();
```

### View Logs
- Browser DevTools Console (F12)
- Network tab to monitor API calls
- Application tab to view LocalStorage

## 🔗 Related Files

- Backend: `backend/main.py`, `backend/services/`
- Documentation: `docs/plan/frontend_plan.md`
- API Docs: `docs/plan/backend_api.md`

## 📄 License

Internal project for Computer Vision Quality Control System

## 👥 Support

For issues or feature requests, contact the development team.

---

**Last Updated**: 2024  
**Version**: 1.0.0  
**Status**: Production Ready
