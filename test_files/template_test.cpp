#include <type_traits>
#include <utility>

// 1. 简单的模板元函数 (类型特征)
template <typename T>
struct is_pointer_like {
    static constexpr bool value = std::is_pointer<T>::value || std::is_same<T, std::nullptr_t>::value;
};

// 2. 类型转换特征
template <typename T>
struct add_reference {
    using type = T&;
};

// 3. 使用 enable_if 的 SFINAE
template <typename T, 
          typename = typename std::enable_if<std::is_integral<T>::value>::type>
bool is_positive(T value) {
    return value > 0;
}

// 4. 使用 decltype 的 SFINAE
template <typename T>
auto get_length(const T& container) -> decltype(container.size(), size_t{}) {
    return container.size();
}

// 5. 变参模板
template <typename... Args>
struct type_count {
    static constexpr size_t value = sizeof...(Args);
};

// 6. 变参模板函数
template <typename... Args>
void print_values(Args&&... args) {
    // 只是演示用，不打印实际值
}

// 7. 部分特化
template <typename T, typename U>
struct is_same_type {
    static constexpr bool value = false;
};

template <typename T>
struct is_same_type<T, T> {
    static constexpr bool value = true;
};

// 8. Tag dispatching SFINAE
struct true_type { static constexpr bool value = true; };
struct false_type { static constexpr bool value = false; };

template <typename T>
struct has_to_string_method {
private:
    template <typename C> static true_type test(decltype(&C::to_string));
    template <typename C> static false_type test(...);
public:
    static constexpr bool value = decltype(test<T>(nullptr))::value;
};

// 9. void_t SFINAE 技术
template <typename...>
using void_t = void;

template <typename T, typename = void>
struct has_value_type : std::false_type {};

template <typename T>
struct has_value_type<T, void_t<typename T::value_type>> : std::true_type {};

// 10. 模板模板参数
template <template <typename> class Trait, typename T>
struct apply_trait {
    using type = typename Trait<T>::type;
};

// 11. 新增的条件类型元编程技术 (C++17)
template <bool B, typename T, typename F>
struct conditional {
    using type = F;
};

template <typename T, typename F>
struct conditional<true, T, F> {
    using type = T;
};

// Main 函数，防止编译器警告
int main() {
    bool b1 = is_positive(42);
    bool b2 = is_same_type<int, int>::value;
    
    return 0;
} 