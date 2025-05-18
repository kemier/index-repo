#include <type_traits>
#include <utility>
#include <tuple>
#include <vector>

// 1. Simple template metafunctions (type traits)
template <typename T>
struct is_void_like {
    static constexpr bool value = std::is_same<void, typename std::remove_cv<T>::type>::value;
};

// 2. Type transformation traits
template <typename T>
struct add_const_ref {
    using type = const T&;
};

// 3. SFINAE with enable_if
template <typename T, 
          typename = typename std::enable_if<std::is_integral<T>::value>::type>
bool is_even(T value) {
    return (value % 2) == 0;
}

// 4. SFINAE with decltype
template <typename T>
auto get_size(const T& container) -> decltype(container.size(), size_t{}) {
    return container.size();
}

// 5. Variadic templates
template <typename... Args>
struct pack_size {
    static constexpr size_t value = sizeof...(Args);
};

// 6. Variadic template function
template <typename... Args>
void print_all(Args&&... args) {
    // Fold expression (C++17)
    (std::cout << ... << args) << std::endl;
}

// 7. Template template parameters
template <template <typename> class Trait, typename T>
struct apply_trait {
    using type = typename Trait<T>::type;
};

// Enhanced template template parameter example
template <template <typename...> class Container, typename... Args>
struct container_wrapper {
    using container_type = Container<Args...>;
    
    template <typename... MoreArgs>
    using rebind = container_wrapper<Container, MoreArgs...>;
};

// Example usage of template template parameters
template <typename T, template <typename> class SmartPtr>
class resource_manager {
private:
    SmartPtr<T> resource;
public:
    resource_manager(SmartPtr<T> res) : resource(res) {}
    
    T* get() { return resource.get(); }
};

// 8. Partial specialization
template <typename T, typename U>
struct is_same {
    static constexpr bool value = false;
};

template <typename T>
struct is_same<T, T> {
    static constexpr bool value = true;
};

// 9. Tag dispatching SFINAE
struct true_type { static constexpr bool value = true; };
struct false_type { static constexpr bool value = false; };

template <typename T>
struct has_resize_method {
private:
    template <typename C> static true_type test(decltype(&C::resize));
    template <typename C> static false_type test(...);
public:
    static constexpr bool value = decltype(test<T>(nullptr))::value;
};

// 10. void_t SFINAE technique
template <typename...>
using void_t = void;

template <typename T, typename = void>
struct has_value_type : std::false_type {};

template <typename T>
struct has_value_type<T, void_t<typename T::value_type>> : std::true_type {};

// 11. Metafunction composition
template <typename... Traits>
struct conjunction;

template <typename Trait>
struct conjunction<Trait> : Trait {};

template <typename First, typename... Rest>
struct conjunction<First, Rest...> 
    : std::conditional<First::value, conjunction<Rest...>, First>::type {};

// 12. C++20 Concepts (if compiler supports them)
#if defined(__cpp_concepts) && __cpp_concepts >= 201907L
template <typename T>
concept Addable = requires(T a, T b) {
    { a + b } -> std::convertible_to<T>;
};

template <Addable T>
T add(T a, T b) {
    return a + b;
}
#endif

// 13. Detection idiom (a more modern SFINAE technique)
template <typename Default, typename AlwaysVoid, template<typename...> class Op, typename... Args>
struct detector {
    using value_t = std::false_type;
    using type = Default;
};

template <typename Default, template<typename...> class Op, typename... Args>
struct detector<Default, void_t<Op<Args...>>, Op, Args...> {
    using value_t = std::true_type;
    using type = Op<Args...>;
};

// 14. Expression SFINAE
template <typename T>
auto has_ostream_operator_impl(T* t) -> decltype(std::declval<std::ostream&>() << *t, std::true_type{});
std::false_type has_ostream_operator_impl(...);

template <typename T>
struct has_ostream_operator : decltype(has_ostream_operator_impl(std::declval<T*>())) {};

// 15. Template recursion
template <size_t N>
struct factorial {
    static constexpr size_t value = N * factorial<N-1>::value;
};

template <>
struct factorial<0> {
    static constexpr size_t value = 1;
};

// Main function to prevent compiler warnings
int main() {
    // Test type traits
    static_assert(is_void_like<void>::value, "is_void_like test failed");
    
    // Test SFINAE function
    int n = 42;
    bool is_even_result = is_even(n);
    
    // Test variadic template
    constexpr size_t size = pack_size<int, double, char>::value;
    static_assert(size == 3, "pack_size test failed");
    
    // Test template template parameters
    using int_vector_wrapper = container_wrapper<std::vector, int>;
    using double_vector_wrapper = int_vector_wrapper::rebind<double>;
    
    // Test partial specialization
    static_assert(is_same<int, int>::value, "is_same test failed");
    static_assert(!is_same<int, double>::value, "is_same test failed");
    
    // Test expression SFINAE
    static_assert(has_ostream_operator<int>::value, "has_ostream_operator test failed");
    
    // Test metafunction recursion
    static_assert(factorial<5>::value == 120, "factorial test failed");
    
    return 0;
} 