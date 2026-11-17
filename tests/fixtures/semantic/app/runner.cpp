#include "runner.hpp"
namespace app {
Runner::Runner(domain::Base &service) : service_(service) {}
int Runner::run() const { return service_.calculate(); }
}
