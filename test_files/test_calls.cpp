#include <iostream>
#include <string>

// Simple utility function
void log_message(const std::string& message) {
    std::cout << "LOG: " << message << std::endl;
}

// Another utility function
std::string format_text(const std::string& text) {
    return "[" + text + "]";
}

// A class with methods
class Helper {
public:
    Helper() {}
    
    void print_info() {
        log_message("Helper info");
    }
    
    static std::string get_status() {
        return "OK";
    }
};

// Function that calls other functions
void process_data(const std::string& data) {
    // Call regular function
    log_message("Processing data");
    
    // Call another function
    std::string formatted = format_text(data);
    
    // Create object and call method
    Helper helper;
    helper.print_info();
    
    // Call static method
    std::string status = Helper::get_status();
    
    // Log the result
    log_message("Status: " + status + ", Data: " + formatted);
}

// Main function
int main() {
    process_data("test");
    return 0;
} 