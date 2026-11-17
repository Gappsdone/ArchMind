#pragma once
namespace domain {
class Base {
public:
    virtual ~Base() = default;
    virtual int calculate() const = 0;
};
class Derived : public Base {
public:
    int calculate() const override;
};
}
