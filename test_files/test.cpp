#include <iostream>
#include <string>

class TestClass {
public:
    void hello();
    std::string getMessage();
private:
    std::string message = "Hello, world!";
};

void TestClass::hello() {
    std::cout << getMessage() << std::endl;
}

std::string TestClass::getMessage() {
    return message;
}

int main() {
    TestClass test;
    test.hello();
    return 0;
} 