#include <iostream>
#include <string>

// Example class with operator overloading and implicit conversions
class Complex {
private:
    double real;
    double imag;
    
public:
    // Constructors
    Complex() : real(0), imag(0) {}
    Complex(double r) : real(r), imag(0) {} // implicit conversion from double
    Complex(double r, double i) : real(r), imag(i) {}
    
    // Explicit conversion to bool
    explicit operator bool() const {
        return real != 0 || imag != 0;
    }
    
    // Implicit conversion to double (returns magnitude)
    operator double() const {
        return std::sqrt(real*real + imag*imag);
    }
    
    // Accessor methods
    double getReal() const { return real; }
    double getImag() const { return imag; }
    
    // Member operator overloads
    Complex& operator+=(const Complex& other) {
        real += other.real;
        imag += other.imag;
        return *this;
    }
    
    Complex& operator-=(const Complex& other) {
        real -= other.real;
        imag -= other.imag;
        return *this;
    }
    
    Complex& operator*=(const Complex& other) {
        double newReal = real * other.real - imag * other.imag;
        double newImag = real * other.imag + imag * other.real;
        real = newReal;
        imag = newImag;
        return *this;
    }
    
    Complex operator-() const {
        return Complex(-real, -imag);
    }
    
    Complex operator+() const {
        return *this;
    }
    
    // Subscript operator
    double& operator[](int index) {
        if (index == 0) return real;
        if (index == 1) return imag;
        throw std::out_of_range("Index out of range");
    }
    
    const double& operator[](int index) const {
        if (index == 0) return real;
        if (index == 1) return imag;
        throw std::out_of_range("Index out of range");
    }
    
    // Function call operator
    Complex operator()(double factor) const {
        return Complex(real * factor, imag * factor);
    }
};

// Non-member operator overloads
Complex operator+(const Complex& lhs, const Complex& rhs) {
    Complex result(lhs);
    result += rhs;
    return result;
}

Complex operator-(const Complex& lhs, const Complex& rhs) {
    Complex result(lhs);
    result -= rhs;
    return result;
}

Complex operator*(const Complex& lhs, const Complex& rhs) {
    Complex result(lhs);
    result *= rhs;
    return result;
}

bool operator==(const Complex& lhs, const Complex& rhs) {
    return lhs.getReal() == rhs.getReal() && lhs.getImag() == rhs.getImag();
}

bool operator!=(const Complex& lhs, const Complex& rhs) {
    return !(lhs == rhs);
}

// Stream operators
std::ostream& operator<<(std::ostream& os, const Complex& c) {
    os << c.getReal();
    if (c.getImag() >= 0) {
        os << "+";
    }
    os << c.getImag() << "i";
    return os;
}

std::istream& operator>>(std::istream& is, Complex& c) {
    double real, imag;
    is >> real >> imag;
    c = Complex(real, imag);
    return is;
}

// Class with custom conversion operators
class String {
private:
    std::string data;
    
public:
    String() = default;
    String(const char* str) : data(str) {}
    String(const std::string& str) : data(str) {}
    
    // Conversion to C string
    operator const char*() const {
        return data.c_str();
    }
    
    // Conversion to std::string
    operator std::string() const {
        return data;
    }
    
    // String concatenation operator
    String& operator+=(const String& other) {
        data += other.data;
        return *this;
    }
};

// Non-member string concatenation
String operator+(const String& lhs, const String& rhs) {
    String result(lhs);
    result += rhs;
    return result;
}

// Class with proxy object pattern
class Array {
private:
    int* data;
    size_t size;
    
    // Proxy class for implementing operator[][]
    class Proxy {
    private:
        int* row;
        size_t cols;
        
    public:
        Proxy(int* r, size_t c) : row(r), cols(c) {}
        
        int& operator[](size_t col) {
            if (col >= cols) throw std::out_of_range("Column index out of range");
            return row[col];
        }
        
        const int& operator[](size_t col) const {
            if (col >= cols) throw std::out_of_range("Column index out of range");
            return row[col];
        }
    };
    
public:
    Array(size_t rows, size_t cols) : size(rows * cols) {
        data = new int[rows * cols]();
    }
    
    ~Array() {
        delete[] data;
    }
    
    // Row accessor returns a proxy object
    Proxy operator[](size_t row) {
        if (row >= size) throw std::out_of_range("Row index out of range");
        return Proxy(data + row * 10, 10); // Assuming 10 columns
    }
    
    const Proxy operator[](size_t row) const {
        if (row >= size) throw std::out_of_range("Row index out of range");
        return Proxy(data + row * 10, 10); // Assuming 10 columns
    }
};

// Main function
int main() {
    // Test Complex class
    Complex a(3, 4);
    Complex b(1, 2);
    
    Complex c = a + b;
    Complex d = a * b;
    Complex e = -a;
    
    double magnitude = a; // Implicit conversion to double
    
    if (a) { // Explicit conversion to bool
        std::cout << "Complex number is non-zero" << std::endl;
    }
    
    std::cout << "a = " << a << std::endl;
    std::cout << "b = " << b << std::endl;
    std::cout << "a + b = " << c << std::endl;
    std::cout << "a * b = " << d << std::endl;
    std::cout << "-a = " << e << std::endl;
    std::cout << "Magnitude of a = " << magnitude << std::endl;
    
    // Test String class
    String s1("Hello, ");
    String s2("world!");
    String s3 = s1 + s2;
    
    std::string stdStr = s3; // Implicit conversion to std::string
    const char* cStr = s3;   // Implicit conversion to const char*
    
    std::cout << stdStr << std::endl;
    std::cout << cStr << std::endl;
    
    // Test Array class with proxy pattern
    Array arr(5, 10);
    arr[2][3] = 42; // Use proxy object
    
    std::cout << "arr[2][3] = " << arr[2][3] << std::endl;
    
    return 0;
} 