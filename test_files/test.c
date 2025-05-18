#include <stdio.h>

void helper_function();
void utility_function();
void process_data();

int main() {
    printf("Hello, world!\n");
    helper_function();
    process_data();
    return 0;
}

void helper_function() {
    utility_function();
    printf("Helper function\n");
}

void utility_function() {
    printf("Utility function\n");
}

// This function calls a missing function
void process_data() {
    printf("Processing data...\n");
    missing_function(); // This function is not defined anywhere
} 