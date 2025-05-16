#include "order_system.h"
#include <algorithm>
#include <stdexcept>

OrderSystem::OrderSystem() {}

void OrderSystem::set_handler(const OrderHandler& handler) {
    handler_ = handler;
}

void OrderSystem::create_order(int order_id, double amount) {
    Order order{order_id, amount, "created"};
    validate_order(order);
    orders_.push_back(order);
    
    if (handler_.on_order_created) {
        handler_.on_order_created(order);
    }
}

void OrderSystem::update_order(int order_id, const std::string& status) {
    auto it = std::find_if(orders_.begin(), orders_.end(),
        [order_id](const Order& order) { return order.order_id == order_id; });
    
    if (it != orders_.end()) {
        it->status = status;
        if (handler_.on_order_updated) {
            handler_.on_order_updated(*it);
        }
    }
}

void OrderSystem::complete_order(int order_id) {
    auto it = std::find_if(orders_.begin(), orders_.end(),
        [order_id](const Order& order) { return order.order_id == order_id; });
    
    if (it != orders_.end()) {
        it->status = "completed";
        if (handler_.on_order_completed) {
            handler_.on_order_completed(*it);
        }
    }
}

double OrderSystem::calculate_total_price(const std::vector<Order>& orders) {
    double total = 0.0;
    for (const auto& order : orders) {
        double price = order.amount;
        price = apply_discount(price);
        price = calculate_tax(price);
        total += price;
    }
    return total;
}

double OrderSystem::apply_discount(double price) {
    if (price > 1000.0) {
        return price * 0.9;  // 10% 折扣
    }
    return price;
}

double OrderSystem::calculate_tax(double price) {
    return price * 1.1;  // 10% 税率
}

void OrderSystem::validate_order(const Order& order) {
    if (order.amount <= 0) {
        throw std::invalid_argument("Order amount must be positive");
    }
} 