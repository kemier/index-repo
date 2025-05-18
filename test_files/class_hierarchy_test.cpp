#include <iostream>
#include <string>
#include <vector>
#include <memory>

// Base abstract class
class Shape {
public:
    Shape() = default;
    virtual ~Shape() = default;
    
    virtual double area() const = 0;
    virtual double perimeter() const = 0;
    virtual void draw() const { std::cout << "Drawing a shape" << std::endl; }
    virtual std::string name() const { return "Shape"; }
};

// First level derived class
class Circle : public Shape {
private:
    double radius;
    
public:
    explicit Circle(double r) : radius(r) {}
    
    double area() const override { return 3.14159 * radius * radius; }
    double perimeter() const override { return 2 * 3.14159 * radius; }
    std::string name() const override { return "Circle"; }
    
    // Non-virtual method
    double getRadius() const { return radius; }
};

// First level derived class
class Polygon : public Shape {
protected:
    int sides;
    
public:
    explicit Polygon(int s) : sides(s) {}
    virtual ~Polygon() = default;
    
    // Only partially implement the interface
    double perimeter() const override = 0;
    std::string name() const override { return "Polygon"; }
    
    // Additional virtual method
    virtual int getSides() const { return sides; }
};

// Second level derived class with multiple inheritance
class Rectangle : public Polygon {
private:
    double width;
    double height;
    
public:
    Rectangle(double w, double h) : Polygon(4), width(w), height(h) {}
    
    double area() const override { return width * height; }
    double perimeter() const override { return 2 * (width + height); }
    std::string name() const override { return "Rectangle"; }
    
    // Overloaded operators
    bool operator==(const Rectangle& other) const {
        return width == other.width && height == other.height;
    }
    
    // Friend function
    friend std::ostream& operator<<(std::ostream& os, const Rectangle& rect);
};

// Operator overloading - friend function implementation
std::ostream& operator<<(std::ostream& os, const Rectangle& rect) {
    os << "Rectangle[" << rect.width << "x" << rect.height << "]";
    return os;
}

// Third level derived class
class Square : public Rectangle {
public:
    explicit Square(double side) : Rectangle(side, side) {}
    
    std::string name() const override { return "Square"; }
};

// Template class with inheritance
template <typename T>
class ColoredShape : public Shape {
private:
    Shape* baseShape;
    T color;
    
public:
    ColoredShape(Shape* shape, T c) : baseShape(shape), color(c) {}
    ~ColoredShape() override = default;
    
    double area() const override { return baseShape->area(); }
    double perimeter() const override { return baseShape->perimeter(); }
    std::string name() const override { 
        return "Colored" + baseShape->name(); 
    }
    
    // Template method
    T getColor() const { return color; }
};

// Diamond inheritance example
class DrawableShape : public virtual Shape {
protected:
    std::string style;
    
public:
    explicit DrawableShape(const std::string& s) : style(s) {}
    virtual ~DrawableShape() = default;
    
    void draw() const override {
        std::cout << "Drawing with style: " << style << std::endl;
    }
};

class ColoredPolygon : public Polygon, public DrawableShape {
private:
    std::string color;
    
public:
    ColoredPolygon(int sides, const std::string& style, const std::string& color)
        : Polygon(sides), DrawableShape(style), color(color) {}
    
    double area() const override { return 0; } // placeholder implementation
    double perimeter() const override { return 0; } // placeholder implementation
    std::string name() const override { 
        return color + " " + Polygon::name() + " with " + style; 
    }
};

// Main function for testing
int main() {
    // Create shape collection
    std::vector<std::unique_ptr<Shape>> shapes;
    
    shapes.push_back(std::make_unique<Circle>(5.0));
    shapes.push_back(std::make_unique<Square>(4.0));
    shapes.push_back(std::make_unique<ColoredShape<std::string>>(new Circle(3.0), "red"));
    shapes.push_back(std::make_unique<ColoredPolygon>(6, "dashed", "blue"));
    
    // Test virtual function calls
    for (const auto& shape : shapes) {
        std::cout << "Shape: " << shape->name() << std::endl;
        std::cout << "Area: " << shape->area() << std::endl;
        std::cout << "Perimeter: " << shape->perimeter() << std::endl;
        shape->draw();
        std::cout << "-------------------" << std::endl;
    }
    
    // Test operator overloading
    Rectangle r1(3, 4);
    Rectangle r2(3, 4);
    Rectangle r3(5, 6);
    
    std::cout << "r1 == r2: " << (r1 == r2) << std::endl;
    std::cout << "r1 == r3: " << (r1 == r3) << std::endl;
    std::cout << "r1: " << r1 << std::endl;
    
    return 0;
} 