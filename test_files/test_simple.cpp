#include <iostream>

// Simple function without calls
void simple_function() {
    std::cout << "This is a simple function" << std::endl;
}

// Function that calls another function
void caller_function() {
    std::cout << "This function calls another" << std::endl;
    simple_function();
}

// Main function
int main() {
    std::cout << "Hello World" << std::endl;
    caller_function();
    return 0;
} 