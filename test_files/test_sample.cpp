#include <iostream>

// Simple utility function
int add(int a, int b) {
    return a + b;
}

// Function that calls another function
int multiply(int a, int b) {
    return a * b;
}

// Function with multiple calls
int calculate(int a, int b) {
    int sum = add(a, b);
    int product = multiply(a, b);
    return sum + product;
}

// Main entry point
int main() {
    int result = calculate(5, 3);
    std::cout << "Result: " << result << std::endl;
    return 0;
} 