#!/bin/bash
# Fix dependencies after npm audit fix --force broke react-scripts

echo "Cleaning up node_modules and package-lock.json..."
rm -rf node_modules package-lock.json

echo "Installing dependencies..."
npm install

echo "Verifying react-scripts installation..."
if [ -f "node_modules/.bin/react-scripts" ]; then
    echo "✓ react-scripts installed successfully!"
    echo "You can now run: npm run build"
else
    echo "✗ react-scripts installation failed"
    echo "Try: npm install react-scripts@5.0.1 --save"
fi

