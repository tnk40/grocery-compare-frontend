// API Configuration - Change this to your Railway backend URL
const API_URL = 'https://backend-production-5565.up.railway.app';

// State
let token = localStorage.getItem('token');
let basket = [];
let prices = [];
let items = [];

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    if (token) {
        showMainApp();
    }
});

// Auth Functions
async function register() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            token = data.access_token;
            localStorage.setItem('token', token);
            showMainApp();
        } else {
            showAuthError(data.detail || 'Registration failed');
        }
    } catch (error) {
        showAuthError('Connection error. Is the backend running?');
    }
}

async function login() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            token = data.access_token;
            localStorage.setItem('token', token);
            showMainApp();
        } else {
            showAuthError(data.detail || 'Login failed');
        }
    } catch (error) {
        showAuthError('Connection error. Is the backend running?');
    }
}

function logout() {
    token = null;
    localStorage.removeItem('token');
    basket = [];
    document.getElementById('login-section').style.display = 'flex';
    document.getElementById('main-section').style.display = 'none';
}

function showAuthError(message) {
    document.getElementById('auth-message').textContent = message;
}

// Main App
async function showMainApp() {
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('main-section').style.display = 'block';
    
    // Get user info
    try {
        const response = await fetch(`${API_URL}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const user = await response.json();
            document.getElementById('user-email').textContent = user.email;
        } else {
            logout();
            return;
        }
    } catch (error) {
        logout();
        return;
    }
    
    // Load data
    await loadPrices();
    await loadItems();
    await loadSavedLists();
}

async function loadPrices() {
    try {
        const response = await fetch(`${API_URL}/prices`);
        prices = await response.json();
    } catch (error) {
        console.error('Failed to load prices:', error);
    }
}

async function loadItems() {
    try {
        const response = await fetch(`${API_URL}/prices/items`);
        items = await response.json();
        
        const picker = document.getElementById('item-picker');
        picker.innerHTML = '<option value="">Select an item...</option>';
        
        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item.item;
            option.textContent = `${item.item} (${item.category})`;
            picker.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load items:', error);
    }
}

// Basket Functions
function addToBasket() {
    const picker = document.getElementById('item-picker');
    const quantity = parseInt(document.getElementById('quantity').value) || 1;
    const itemName = picker.value;
    
    if (!itemName) return;
    
    const existing = basket.find(b => b.item === itemName);
    if (existing) {
        existing.quantity += quantity;
    } else {
        basket.push({ item: itemName, quantity });
    }
    
    picker.value = '';
    document.getElementById('quantity').value = 1;
    
    renderBasket();
    calculatePrices();
}

function removeFromBasket(index) {
    basket.splice(index, 1);
    renderBasket();
    calculatePrices();
}

function clearBasket() {
    basket = [];
    renderBasket();
    calculatePrices();
}

function renderBasket() {
    const tbody = document.getElementById('basket-body');
    tbody.innerHTML = '';
    
    basket.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${item.item}</td>
            <td>${item.quantity}</td>
            <td><button class="remove-btn" onclick="removeFromBasket(${index})">×</button></td>
        `;
        tbody.appendChild(row);
    });
}

// Price Calculation
function calculatePrices() {
    if (basket.length === 0) {
        document.getElementById('recommendations-body').innerHTML = '';
        document.getElementById('totals-body').innerHTML = '';
        document.getElementById('savings-text').textContent = '';
        return;
    }
    
    // Find cheapest store for each item
    const recommendations = [];
    const storeTotals = {};
    
    basket.forEach(basketItem => {
        const itemPrices = prices.filter(p => p.item === basketItem.item);
        
        if (itemPrices.length > 0) {
            // Find cheapest
            const cheapest = itemPrices.reduce((min, p) => 
                p.price_per_unit_gbp < min.price_per_unit_gbp ? p : min
            );
            
            recommendations.push({
                item: basketItem.item,
                store: cheapest.store,
                price: cheapest.price_per_unit_gbp * basketItem.quantity,
                quantity: basketItem.quantity
            });
            
            // Calculate totals per store
            itemPrices.forEach(p => {
                if (!storeTotals[p.store]) {
                    storeTotals[p.store] = 0;
                }
                storeTotals[p.store] += p.price_per_unit_gbp * basketItem.quantity;
            });
        }
    });
    
    // Render recommendations
    const recBody = document.getElementById('recommendations-body');
    recBody.innerHTML = '';
    recommendations.forEach(rec => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${rec.item}</td>
            <td>${rec.store}</td>
            <td>£${rec.price.toFixed(2)}</td>
        `;
        recBody.appendChild(row);
    });
    
    // Render store totals
    const totalsBody = document.getElementById('totals-body');
    totalsBody.innerHTML = '';
    
    const sortedStores = Object.entries(storeTotals)
        .sort((a, b) => a[1] - b[1]);
    
    const cheapestTotal = sortedStores[0]?.[1] || 0;
    const mostExpensive = sortedStores[sortedStores.length - 1]?.[1] || 0;
    
    sortedStores.forEach(([store, total], index) => {
        const row = document.createElement('tr');
        if (index === 0) {
            row.className = 'cheapest';
        }
        row.innerHTML = `
            <td>${store}${index === 0 ? ' ✓' : ''}</td>
            <td>£${total.toFixed(2)}</td>
        `;
        totalsBody.appendChild(row);
    });
    
    // Show savings
    const savings = mostExpensive - cheapestTotal;
    if (savings > 0) {
        document.getElementById('savings-text').textContent = 
            `You could save £${savings.toFixed(2)} by shopping at ${sortedStores[0][0]}!`;
    } else {
        document.getElementById('savings-text').textContent = '';
    }
}

// Saved Lists
async function loadSavedLists() {
    try {
        const response = await fetch(`${API_URL}/lists`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const lists = await response.json();
            renderSavedLists(lists);
        }
    } catch (error) {
        console.error('Failed to load lists:', error);
    }
}

function renderSavedLists(lists) {
    const container = document.getElementById('saved-lists');
    container.innerHTML = '';
    
    if (lists.length === 0) {
        container.innerHTML = '<p style="color: #7f8c8d;">No saved lists yet</p>';
        return;
    }
    
    lists.forEach(list => {
        const div = document.createElement('div');
        div.className = 'saved-list-item';
        div.innerHTML = `
            <span>${list.name} (${list.items.length} items)</span>
            <div class="saved-list-actions">
                <button class="btn btn-small btn-primary" onclick="loadList(${list.id})">Load</button>
                <button class="btn btn-small btn-danger" onclick="deleteList(${list.id})">Delete</button>
            </div>
        `;
        container.appendChild(div);
    });
}

async function saveList() {
    const name = document.getElementById('list-name').value || 'My Shopping List';
    
    if (basket.length === 0) {
        document.getElementById('save-message').textContent = 'Basket is empty!';
        return;
    }
    
    const items = basket.map(b => ({
        item_name: b.item,
        quantity: b.quantity
    }));
    
    try {
        const response = await fetch(`${API_URL}/lists`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ name, items })
        });
        
        if (response.ok) {
            document.getElementById('save-message').textContent = 'List saved!';
            document.getElementById('list-name').value = '';
            await loadSavedLists();
            setTimeout(() => {
                document.getElementById('save-message').textContent = '';
            }, 2000);
        } else {
            document.getElementById('save-message').textContent = 'Failed to save list';
        }
    } catch (error) {
        document.getElementById('save-message').textContent = 'Error saving list';
    }
}

async function loadList(listId) {
    try {
        const response = await fetch(`${API_URL}/lists/${listId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const list = await response.json();
            basket = list.items.map(i => ({
                item: i.item_name,
                quantity: i.quantity
            }));
            document.getElementById('list-name').value = list.name;
            renderBasket();
            calculatePrices();
        }
    } catch (error) {
        console.error('Failed to load list:', error);
    }
}

async function deleteList(listId) {
    if (!confirm('Delete this list?')) return;
    
    try {
        const response = await fetch(`${API_URL}/lists/${listId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            await loadSavedLists();
        }
    } catch (error) {
        console.error('Failed to delete list:', error);
    }
}