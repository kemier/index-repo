#include <iostream>
#include <concepts>
#include <type_traits>
#include <string>
#include <vector>

// Basic concept definition
template <typename T>
concept Integral = std::is_integral_v<T>;

// Concept with a compound requirement
template <typename T>
concept Numeric = std::is_arithmetic_v<T> && 
                 requires(T a, T b) {
                     { a + b } -> std::convertible_to<T>;
                     { a - b } -> std::convertible_to<T>;
                     { a * b } -> std::convertible_to<T>;
                     { a / b } -> std::convertible_to<T>;
                 };

// Concept with a nested requirement
template <typename T>
concept Comparable = requires(T a, T b) {
    { a == b } -> std::convertible_to<bool>;
    { a != b } -> std::convertible_to<bool>;
    requires std::totally_ordered<T>;
};

// Concept with a type requirement
template <typename T>
concept Container = requires(T container) {
    typename T::value_type;
    typename T::iterator;
    typename T::const_iterator;
    { container.begin() } -> std::same_as<typename T::iterator>;
    { container.end() } -> std::same_as<typename T::iterator>;
    { container.size() } -> std::convertible_to<size_t>;
};

// Concept using other concepts (refinement)
template <typename T>
concept Number = Integral<T> || std::floating_point<T>;

// Function template using a concept constraint
template <Integral T>
T gcd(T a, T b) {
    if (b == 0)
        return a;
    return gcd(b, a % b);
}

// Function with multiple concept constraints
template <Numeric T>
requires std::default_initializable<T>
T zero() {
    return T{};
}

// Class template with concept constraints
template <Container T>
class ContainerWrapper {
private:
    T container;
public:
    ContainerWrapper(const T& c) : container(c) {}
    
    auto begin() { return container.begin(); }
    auto end() { return container.end(); }
    
    size_t size() const { return container.size(); }
};

// Using auto parameters with concept constraints
void print_number(Number auto const& n) {
    std::cout << "Number: " << n << std::endl;
}

// Function with requires clause in body
template <typename T>
void process(T value) {
    // Compile-time constraint check
    requires Numeric<T>;
    
    // Function body
    T result = value * value;
    std::cout << "Processed: " << result << std::endl;
}

// Conjunction of concepts
template <typename T>
concept SerializableNumeric = Numeric<T> && requires(T a) {
    { a.serialize() } -> std::convertible_to<std::string>;
};

// Different forms of concept usage
template <typename T>
    requires Integral<T>
T increment_v1(T x) {
    return x + 1;
}

template <Integral T>
T increment_v2(T x) {
    return x + 1;
}

Integral auto increment_v3(Integral auto x) {
    return x + 1;
}

// Partial specialization with concepts
template <typename T>
struct Traits {
    static constexpr bool is_supported = false;
};

template <Numeric T>
struct Traits<T> {
    static constexpr bool is_supported = true;
};

// Multi-parameter concepts
template <typename T, typename U>
concept Addable = requires(T t, U u) {
    { t + u };
};

template <typename T, typename U>
    requires Addable<T, U>
auto add(T a, U b) {
    return a + b;
}

int main() {
    // Testing concept-constrained functions
    std::cout << "GCD of 48 and 18: " << gcd(48, 18) << std::endl;
    
    std::cout << "Zero for int: " << zero<int>() << std::endl;
    std::cout << "Zero for double: " << zero<double>() << std::endl;
    
    // Testing concept-constrained class
    std::vector<int> vec = {1, 2, 3, 4, 5};
    ContainerWrapper wrapper(vec);
    std::cout << "Container size: " << wrapper.size() << std::endl;
    
    // Using auto parameter with concept constraint
    print_number(42);
    print_number(3.14159);
    
    // Using concept for constraint checking at compile time
    process(10);
    // process("hello");  // Error: Constraint not satisfied
    
    return 0;
} 