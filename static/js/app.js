// No authentication needed for single-user PoC
// Load dashboard directly
document.addEventListener('DOMContentLoaded', function() {
    // Hide auth buttons and show dashboard
    document.getElementById('auth-buttons').style.display = 'none';
    document.getElementById('user-info').style.display = 'none';
    document.getElementById('dashboard').style.display = 'grid';
    
    // Load dashboard data
    loadDashboardData();
});

async function loadDashboardData() {
    try {
        // Load dashboard stats directly (no authentication needed)
        const statsResponse = await fetch('/api/dashboard/stats');
        
        if (!statsResponse.ok) {
            throw new Error('Failed to load dashboard data');
        }
        
        const stats = await statsResponse.json();
        
        // Update stats cards
        document.getElementById('total-orders').textContent = stats.total_orders;
        document.getElementById('grocery-orders').textContent = stats.grocery_orders;
        document.getElementById('grocery-spending').textContent = '$' + stats.grocery_spending.toFixed(2);
        
        // Update top stores
        updateTopStores('top-grocery-stores', stats.top_grocery_stores);
        
        // Create spending chart by store
        createSpendingChart(stats.store_spending_breakdown);
        
        // Load recent orders
        loadRecentOrders();
        
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        document.getElementById('loading').innerHTML = '<div class="error">Error loading data. Please try again.</div>';
    }
}

function updateTopStores(elementId, stores) {
    const element = document.getElementById(elementId);
    if (stores.length === 0) {
        element.innerHTML = '<p>No data available</p>';
        return;
    }
    
    let html = '<ul style="list-style: none; padding: 0;">';
    stores.forEach((store, index) => {
        html += `<li style="padding: 8px 0; border-bottom: 1px solid #ecf0f1;">
            <strong>${index + 1}.</strong> ${store[0]} <span style="color: #3498db;">(${store[1]} orders)</span>
        </li>`;
    });
    html += '</ul>';
    element.innerHTML = html;
}

function createSpendingChart(storeSpendingData) {
    const ctx = document.getElementById('spendingChart').getContext('2d');
    
    // Prepare data for chart
    const labels = storeSpendingData.map(item => item.store);
    const data = storeSpendingData.map(item => item.spending);
    
    // Generate colors for each store
    const colors = [
        '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
        '#1abc9c', '#34495e', '#e67e22', '#95a5a6', '#f1c40f'
    ];
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            return `${label}: $${value.toFixed(2)}`;
                        }
                    }
                }
            }
        }
    });
}

async function loadRecentOrders() {
    try {
        // Load recent orders directly (no authentication needed)
        const groceryResponse = await fetch('/api/orders/grocery?limit=5');
        const groceryData = await groceryResponse.json();
        updateRecentOrders('recent-grocery-orders', groceryData.orders, 'grocery');
        
        // Load grocery items
        loadGroceryItems();
        
    } catch (error) {
        console.error('Error loading recent orders:', error);
    }
}

async function loadGroceryItems() {
    try {
        const response = await fetch('/api/items/grocery');
        const data = await response.json();
        
        if (data.items) {
            updateGroceryItems(data.items);
        }
    } catch (error) {
        console.error('Error loading grocery items:', error);
    }
}

function updateGroceryItems(items) {
    const element = document.getElementById('top-grocery-items');
    
    if (items.length === 0) {
        element.innerHTML = '<p>No grocery items found</p>';
        return;
    }
    
    // Store items globally for search functionality
    window.allGroceryItems = items;
    
    // Show top 10 items
    const topItems = items.slice(0, 10);
    
    let html = `
        <div class="search-container">
            <input type="text" id="grocery-search" placeholder="🔍 Search grocery items..." class="search-input">
        </div>
        <div class="items-list" id="grocery-items-list">
    `;
    
    topItems.forEach((item, index) => {
        const latestDate = item.latest_bought ? new Date(item.latest_bought).toLocaleDateString() : 'N/A';
        html += `
            <div class="item-row" data-item-name="${item.name}">
                <div class="item-rank">${index + 1}</div>
                <div class="item-details">
                    <div class="item-name">
                        <span class="item-name-text">${item.name}</span>
                        <button class="edit-btn" onclick="editItemName('${item.name}')" title="Edit name">✏️</button>
                        <button class="delete-btn" onclick="deleteItem('${item.name}')" title="Delete item">🗑️</button>
                    </div>
                    <div class="item-stats">
                        <span class="quantity">Qty: ${item.total_quantity}</span>
                        <span class="times">Bought: ${item.times_bought}x</span>
                        <span class="spent">$${item.total_spent.toFixed(2)}</span>
                        <span class="latest">Latest: ${latestDate}</span>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    // Add "View All Items" link
    html += `
        <div class="view-all-container">
            <button onclick="showAllItems()" class="view-all-btn">
                📋 View All ${items.length} Unique Items
            </button>
        </div>
    `;
    
    element.innerHTML = html;
    
    // Add search functionality
    const searchInput = document.getElementById('grocery-search');
    searchInput.addEventListener('input', function() {
        filterGroceryItems(this.value);
    });
}

async function showAllItems() {
    // Load items data first
    try {
        const response = await fetch('/api/items/grocery');
        const data = await response.json();
        
        if (data.items) {
            window.allItems = data.items;
            
            // Create modal for all items
            const modal = document.createElement('div');
            modal.className = 'items-modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>🛍️ All Grocery Items (${data.items.length} unique)</h3>
                        <button onclick="closeModal()" class="close-btn">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div id="all-items-list"></div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Display all items
            displayAllItems(data.items);
        }
    } catch (error) {
        console.error('Error loading items for modal:', error);
    }
}

// Make functions globally accessible
window.showAllItems = showAllItems;


function displayAllItems(items) {
    const element = document.getElementById('all-items-list');
    
    let html = '<div class="all-items-list">';
    items.forEach((item, index) => {
        const latestDate = item.latest_bought ? new Date(item.latest_bought).toLocaleDateString() : 'N/A';
        html += `
            <div class="all-item-row">
                <div class="item-rank">${index + 1}</div>
                <div class="item-details">
                    <div class="item-name">${item.name}</div>
                    <div class="item-stats">
                        <span class="quantity">Qty: ${item.total_quantity}</span>
                        <span class="times">Bought: ${item.times_bought}x</span>
                        <span class="spent">$${item.total_spent.toFixed(2)}</span>
                        <span class="latest">Latest: ${latestDate}</span>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    element.innerHTML = html;
}

function closeModal() {
    const modal = document.querySelector('.items-modal');
    if (modal) {
        modal.remove();
    }
}

// Make functions globally accessible
window.closeModal = closeModal;

function updateRecentOrders(elementId, orders, type) {
    const element = document.getElementById(elementId);
    if (orders.length === 0) {
        element.innerHTML = '<p>No recent orders</p>';
        return;
    }
    
    let html = '<div style="max-height: 300px; overflow-y: auto;">';
    orders.forEach(order => {
        const total = order.totals?.total || 0;
        const store = order.store_name || 'Unknown Store';
        const date = order.date || 'Unknown Date';
        const itemCount = order.items?.length || 0;
        
        html += `<div style="padding: 10px; border-bottom: 1px solid #ecf0f1; margin-bottom: 10px;">
            <div style="font-weight: bold; color: #2c3e50;">${store}</div>
            <div style="color: #7f8c8d; font-size: 0.9em;">${date} • ${itemCount} items</div>
            <div style="color: #27ae60; font-weight: bold;">$${total.toFixed(2)}</div>
        </div>`;
    });
    html += '</div>';
    element.innerHTML = html;
}

// Item editing functions
function editItemName(itemName) {
    const itemRow = document.querySelector(`[data-item-name="${itemName}"]`);
    const nameElement = itemRow.querySelector('.item-name-text');
    const editBtn = itemRow.querySelector('.edit-btn');
    
    // Create input field
    const input = document.createElement('input');
    input.type = 'text';
    input.value = itemName;
    input.className = 'item-name-input';
    input.style.width = '100%';
    input.style.padding = '4px';
    input.style.border = '1px solid #ddd';
    input.style.borderRadius = '4px';
    
    // Replace text with input
    nameElement.style.display = 'none';
    editBtn.style.display = 'none';
    
    const inputContainer = document.createElement('div');
    inputContainer.style.display = 'flex';
    inputContainer.style.gap = '5px';
    inputContainer.style.alignItems = 'center';
    
    inputContainer.appendChild(input);
    
    // Add save/cancel buttons
    const saveBtn = document.createElement('button');
    saveBtn.textContent = '✓';
    saveBtn.className = 'save-btn';
    saveBtn.style.background = '#27ae60';
    saveBtn.style.color = 'white';
    saveBtn.style.border = 'none';
    saveBtn.style.padding = '4px 8px';
    saveBtn.style.borderRadius = '4px';
    saveBtn.style.cursor = 'pointer';
    saveBtn.onclick = () => saveItemName(itemName, input.value);
    
    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = '✗';
    cancelBtn.className = 'cancel-btn';
    cancelBtn.style.background = '#e74c3c';
    cancelBtn.style.color = 'white';
    cancelBtn.style.border = 'none';
    cancelBtn.style.padding = '4px 8px';
    cancelBtn.style.borderRadius = '4px';
    cancelBtn.style.cursor = 'pointer';
    cancelBtn.onclick = () => cancelEdit(itemName);
    
    inputContainer.appendChild(saveBtn);
    inputContainer.appendChild(cancelBtn);
    
    // Replace the name element with input container
    nameElement.parentNode.insertBefore(inputContainer, nameElement);
    
    // Focus and select the input
    input.focus();
    input.select();
}

async function saveItemName(oldName, newName) {
    if (oldName === newName) {
        cancelEdit(oldName);
        return;
    }
    
    try {
        const response = await fetch('/api/items/grocery/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                old_name: oldName,
                new_name: newName
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Reload the grocery items to show updated data
            await loadGroceryItems();
            alert(`Successfully updated ${result.updated_count} items from "${oldName}" to "${newName}"`);
        } else {
            alert('Error updating item: ' + result.error);
        }
    } catch (error) {
        console.error('Error updating item:', error);
        alert('Error updating item. Please try again.');
    }
}

function cancelEdit(itemName) {
    const itemRow = document.querySelector(`[data-item-name="${itemName}"]`);
    const nameElement = itemRow.querySelector('.item-name-text');
    const editBtn = itemRow.querySelector('.edit-btn');
    const inputContainer = itemRow.querySelector('.item-name-input').parentNode;
    
    // Restore original display
    nameElement.style.display = 'inline';
    editBtn.style.display = 'inline';
    
    // Remove input container
    inputContainer.remove();
}

async function deleteItem(itemName) {
    // Show confirmation dialog
    const confirmed = confirm(`Are you sure you want to delete "${itemName}"?\n\nThis will permanently remove all instances of this item from your database.`);
    
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch('/api/items/grocery/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                item_name: itemName
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Reload the grocery items to show updated data
            await loadGroceryItems();
            alert(`Successfully deleted ${result.updated_count} instances of "${itemName}"`);
        } else {
            alert('Error deleting item: ' + result.error);
        }
    } catch (error) {
        console.error('Error deleting item:', error);
        alert('Error deleting item. Please try again.');
    }
}

function filterGroceryItems(searchTerm) {
    if (!window.allGroceryItems) return;
    
    const filteredItems = window.allGroceryItems.filter(item => 
        item.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
    
    const itemsList = document.getElementById('grocery-items-list');
    if (!itemsList) return;
    
    // Clear current items
    itemsList.innerHTML = '';
    
    // Show filtered items (limit to 10 for main view)
    const displayItems = filteredItems.slice(0, 10);
    
    displayItems.forEach((item, index) => {
        const latestDate = item.latest_bought ? new Date(item.latest_bought).toLocaleDateString() : 'N/A';
        const itemRow = document.createElement('div');
        itemRow.className = 'item-row';
        itemRow.setAttribute('data-item-name', item.name);
        
        itemRow.innerHTML = `
            <div class="item-rank">${index + 1}</div>
            <div class="item-details">
                <div class="item-name">
                    <span class="item-name-text">${item.name}</span>
                    <button class="edit-btn" onclick="editItemName('${item.name}')" title="Edit name">✏️</button>
                    <button class="delete-btn" onclick="deleteItem('${item.name}')" title="Delete item">🗑️</button>
                </div>
                <div class="item-stats">
                    <span class="quantity">Qty: ${item.total_quantity}</span>
                    <span class="times">Bought: ${item.times_bought}x</span>
                    <span class="spent">$${item.total_spent.toFixed(2)}</span>
                    <span class="latest">Latest: ${latestDate}</span>
                </div>
            </div>
        `;
        
        itemsList.appendChild(itemRow);
    });
    
    // Update "View All Items" button text
    const viewAllBtn = document.querySelector('.view-all-btn');
    if (viewAllBtn) {
        viewAllBtn.textContent = `📋 View All ${filteredItems.length} Unique Items`;
    }
}

// Make functions globally accessible
window.showAllItems = showAllItems;
window.closeModal = closeModal;
window.editItemName = editItemName;
window.saveItemName = saveItemName;
window.cancelEdit = cancelEdit;
window.deleteItem = deleteItem;
