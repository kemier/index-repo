#pragma once
#include <string>
#include <functional>
#include <vector>

// 订单结构体
struct Order {
    int order_id;
    double amount;
    std::string status;
};

// 订单处理器回调函数类型
using OrderCallback = std::function<void(const Order&)>;

// 订单处理器结构体
struct OrderHandler {
    OrderCallback on_order_created;
    OrderCallback on_order_updated;
    OrderCallback on_order_completed;
};

// 订单系统类
class OrderSystem {
public:
    OrderSystem();
    void set_handler(const OrderHandler& handler);
    void create_order(int order_id, double amount);
    void update_order(int order_id, const std::string& status);
    void complete_order(int order_id);
    double calculate_total_price(const std::vector<Order>& orders);

private:
    OrderHandler handler_;
    std::vector<Order> orders_;
    double apply_discount(double price);
    double calculate_tax(double price);
    void validate_order(const Order& order);
}; 