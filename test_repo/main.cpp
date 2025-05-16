#include "order_system.h"
#include <iostream>

void print_order(const Order& order) {
    std::cout << "Order ID: " << order.order_id
              << ", Amount: " << order.amount
              << ", Status: " << order.status << std::endl;
}

int main() {
    OrderSystem system;
    
    // 设置回调函数
    OrderHandler handler{
        [](const Order& order) {
            std::cout << "Order created: ";
            print_order(order);
        },
        [](const Order& order) {
            std::cout << "Order updated: ";
            print_order(order);
        },
        [](const Order& order) {
            std::cout << "Order completed: ";
            print_order(order);
        }
    };
    
    system.set_handler(handler);
    
    // 创建订单
    system.create_order(1, 500.0);
    system.create_order(2, 1500.0);
    
    // 更新订单状态
    system.update_order(1, "processing");
    
    // 完成订单
    system.complete_order(2);
    
    // 计算总价
    std::vector<Order> orders{
        {1, 500.0, "processing"},
        {2, 1500.0, "completed"}
    };
    
    double total = system.calculate_total_price(orders);
    std::cout << "Total price: " << total << std::endl;
    
    return 0;
} 