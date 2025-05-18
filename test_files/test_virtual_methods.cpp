#include <iostream>
#include <string>
#include <memory>
#include <vector>

// Base class with virtual methods
class Animal {
public:
    Animal(const std::string& name) : name_(name) {}
    virtual ~Animal() = default;
    
    virtual void makeSound() const {
        std::cout << name_ << " makes a generic sound" << std::endl;
    }
    
    virtual std::string getDescription() const {
        return "Animal: " + name_;
    }
    
    // Non-virtual method
    void eat() const {
        std::cout << name_ << " is eating" << std::endl;
        digestFood();
    }

protected:
    // Protected virtual method
    virtual void digestFood() const {
        std::cout << "Processing food generally" << std::endl;
    }

    std::string name_;
};

// First derived class
class Dog : public Animal {
public:
    Dog(const std::string& name, const std::string& breed)
        : Animal(name), breed_(breed) {}
    
    // Override virtual method
    void makeSound() const override {
        std::cout << name_ << " barks loudly!" << std::endl;
    }
    
    std::string getDescription() const override {
        return "Dog: " + name_ + " (" + breed_ + ")";
    }

protected:
    // Override protected method
    void digestFood() const override {
        std::cout << "Dog digesting food quickly" << std::endl;
    }

private:
    std::string breed_;
};

// Second derived class
class Cat : public Animal {
public:
    Cat(const std::string& name, bool isIndoor)
        : Animal(name), is_indoor_(isIndoor) {}
    
    // Override virtual method
    void makeSound() const override {
        std::cout << name_ << " meows softly" << std::endl;
    }
    
    std::string getDescription() const override {
        std::string location = is_indoor_ ? "indoor" : "outdoor";
        return "Cat: " + name_ + " (" + location + ")";
    }
    
    // Additional method specific to Cat
    void purr() const {
        std::cout << name_ << " is purring" << std::endl;
    }

protected:
    // Override protected method
    void digestFood() const override {
        std::cout << "Cat digesting food slowly" << std::endl;
    }

private:
    bool is_indoor_;
};

// Further derived class to test multi-level inheritance
class Kitten : public Cat {
public:
    Kitten(const std::string& name, bool isIndoor, int ageWeeks)
        : Cat(name, isIndoor), age_weeks_(ageWeeks) {}
    
    // Override method again
    void makeSound() const override {
        std::cout << name_ << " makes tiny meows" << std::endl;
    }
    
    std::string getDescription() const override {
        return "Kitten: " + name_ + " (" + std::to_string(age_weeks_) + " weeks old)";
    }

private:
    int age_weeks_;
};

// Multiple inheritance example
class Amphibian {
public:
    Amphibian(bool canSwim) : can_swim_(canSwim) {}
    virtual ~Amphibian() = default;
    
    virtual void swim() const {
        if (can_swim_) {
            std::cout << "Swimming in water" << std::endl;
        } else {
            std::cout << "Cannot swim" << std::endl;
        }
    }

protected:
    bool can_swim_;
};

// Multiple inheritance
class Frog : public Animal, public Amphibian {
public:
    Frog(const std::string& name, bool canSwim)
        : Animal(name), Amphibian(canSwim) {}
    
    void makeSound() const override {
        std::cout << name_ << " croaks!" << std::endl;
    }
    
    void swim() const override {
        std::cout << name_ << " swims with powerful legs" << std::endl;
    }
};

// Function using polymorphism
void makeAnimalSound(const Animal& animal) {
    animal.makeSound();
}

// Template function that works with polymorphic types
template<typename T>
void describeAnimal(const T& animal) {
    std::cout << "Description: " << animal.getDescription() << std::endl;
}

int main() {
    // Create objects
    Dog dog("Rex", "German Shepherd");
    Cat cat("Whiskers", true);
    Kitten kitten("Mittens", true, 8);
    Frog frog("Kermit", true);
    
    // Store in base class pointers to test virtual dispatch
    std::vector<std::unique_ptr<Animal>> animals;
    animals.push_back(std::make_unique<Dog>("Buddy", "Golden Retriever"));
    animals.push_back(std::make_unique<Cat>("Smokey", false));
    animals.push_back(std::make_unique<Kitten>("Tiny", true, 6));
    animals.push_back(std::make_unique<Frog>("Hoppy", true));
    
    // Call virtual methods through base class
    for (const auto& animal : animals) {
        animal->makeSound();
        std::cout << animal->getDescription() << std::endl;
        animal->eat();  // Non-virtual method that calls virtual method
        std::cout << "-------------------" << std::endl;
    }
    
    // Test with free functions
    makeAnimalSound(dog);
    makeAnimalSound(cat);
    makeAnimalSound(frog);
    
    // Test with template function
    describeAnimal(dog);
    describeAnimal(cat);
    describeAnimal(kitten);
    
    // Test multiple inheritance
    frog.swim();
    
    return 0;
} 