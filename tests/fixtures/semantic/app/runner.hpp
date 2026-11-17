#pragma once
#include "base.hpp"
namespace app {
class Runner {
public:
    explicit Runner(domain::Base &service);
    int run() const;
private:
    domain::Base &service_;
};
}
